"""Intent-linked quiet-to-active research selection, never trade authorization.

No ticker list, price ceiling, account balance, or historical-high-volume gate.
Numerical cutoffs are explicit experiment inputs, not approved trading settings.
"""
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from decimal import Decimal as D
import hashlib
import json
from statistics import median

from replay import DataError


@dataclass(frozen=True)
class SelectionPolicy:
    version: str
    bar_minutes: int
    window_bars: int
    prior_sessions: int
    quiet_max_daily_shares: D
    minimum_price_rise: D
    minimum_relative_volume: D
    minimum_window_dollars: D
    cooldown_minutes: int

    def __post_init__(self):
        if not self.version or self.bar_minutes not in (1, 5, 15):
            raise DataError('Explicit policy version and supported bar duration required')
        if (any(not isinstance(v, int) or isinstance(v, bool) for v in
                (self.window_bars, self.prior_sessions, self.cooldown_minutes))
                or self.window_bars < 1 or self.prior_sessions < 2 or self.cooldown_minutes < 0):
            raise DataError('Invalid baseline, window or cooldown')
        for field in ('quiet_max_daily_shares', 'minimum_price_rise',
                      'minimum_relative_volume', 'minimum_window_dollars'):
            value = D(str(getattr(self, field)))
            if not value.is_finite() or value <= 0:
                raise DataError('Explicit finite positive research thresholds required')
            object.__setattr__(self, field, value)
        if self.minimum_relative_volume <= 1:
            raise DataError('Activation must exceed normal activity')

    def fingerprint(self):
        values = {k: str(v) if isinstance(v, D) else v for k, v in asdict(self).items()}
        return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Observation:
    timestamp: int               # UTC bar start, seconds
    session: str                 # Provider-validated exchange session date
    minute: int                  # Minutes after regular-session open
    close: D
    volume: D
    session_minutes: int = 390   # Explicit calendar length, not synthesized missing bars


def validate_observations(observations, policy):
    prior_time = None
    seen = set()
    for row in observations:
        date.fromisoformat(row.session)
        if (row.minute < 0 or row.minute % policy.bar_minutes or
                row.minute + policy.bar_minutes > row.session_minutes or
                row.session_minutes % policy.bar_minutes):
            raise DataError('Invalid session slot or calendar length')
        if row.timestamp < 946684800 or row.timestamp > 4102444800:
            raise DataError('Expected UTC epoch seconds')
        if datetime.fromtimestamp(row.timestamp, timezone.utc).date().isoformat() != row.session:
            raise DataError('US regular-session date disagrees with UTC epoch')
        if prior_time is not None and row.timestamp <= prior_time:
            raise DataError('Duplicate/unordered observations')
        if (row.session, row.minute) in seen:
            raise DataError('Conflicting session-slot revisions')
        for value in (row.close, row.volume):
            if not isinstance(value, D) or not value.is_finite():
                raise DataError('Exact finite price and volume required')
        if row.close <= 0 or row.volume < 0:
            raise DataError('Invalid price or volume')
        prior_time = row.timestamp
        seen.add((row.session, row.minute))


def scan_symbol(symbol, observations, policy, known_discontinuities=()):
    """Return a decision record for every observable window, including failures.

    Historical inputs must have exchange-session labels/calendar lengths supplied
    and qualified by their adapter. Missing bars are unknown, never zero activity.
    """
    validate_observations(observations, policy)
    days = defaultdict(dict)
    day_opens = {}
    day_lengths = {}
    for row in observations:
        days[row.session][row.minute] = row
        day_opens.setdefault(row.session, row.timestamp - row.minute * 60)
        day_lengths.setdefault(row.session, row.session_minutes)
        if (day_opens[row.session] != row.timestamp - row.minute * 60 or
                day_lengths[row.session] != row.session_minutes):
            raise DataError('Epoch, session slots or calendar lengths disagree')
    complete = {}
    for session, slots in days.items():
        length = day_lengths[session]
        if set(slots) == set(range(0, length, policy.bar_minutes)):
            complete[session] = sum((r.volume for r in slots.values()), D(0))
    discontinuities = set(known_discontinuities)
    decisions = []
    last_candidate = None
    policy_sha256 = policy.fingerprint()
    for row in observations:
        available_at = row.timestamp + policy.bar_minutes * 60
        record = dict(symbol=symbol, session=row.session, available_at=available_at,
                      policy_sha256=policy_sha256, state='insufficient_evidence', reasons=[],
                      cohort='unknown', recommendation='not_qualified', execution='not_assessed',
                      missing_execution_evidence=['fresh_quotes', 'remaining_opportunity',
                                                  'protective_exit', 'account_risk_checks'],
                      experimental=True, information_basis='completed_bars_only')
        if row.minute < policy.window_bars * policy.bar_minutes:
            record['reasons'] = ['insufficient_same_session_price_window']
            decisions.append(record)
            continue
        previous_sessions = sorted(s for s in days if s < row.session)
        recent = previous_sessions[-policy.prior_sessions:]
        # Do not cherry-pick older complete days around recent missing evidence.
        if len(recent) < policy.prior_sessions or any(s not in complete for s in recent):
            record['reasons'] = ['incomplete_prior_session_coverage']
            decisions.append(record)
            continue
        start = row.minute - (policy.window_bars - 1) * policy.bar_minutes
        slots = list(range(start, row.minute + 1, policy.bar_minutes))
        reference_minute = row.minute - policy.window_bars * policy.bar_minutes
        current = days[row.session]
        if reference_minute not in current or any(m not in current for m in slots):
            record['reasons'] = ['missing_current_window_bar']
            decisions.append(record)
            continue
        if any(any(m not in days[s] for m in slots) for s in recent):
            record['reasons'] = ['missing_comparable_time_of_day_window']
            decisions.append(record)
            continue
        if any(s in discontinuities for s in recent + [row.session]):
            record['reasons'] = ['unresolved_corporate_action_or_data_discontinuity']
            decisions.append(record)
            continue
        daily_baseline = median([complete[s] for s in recent])
        comparable = [sum((days[s][m].volume for m in slots), D(0)) for s in recent]
        volume_baseline = median(comparable)
        current_volume = sum((current[m].volume for m in slots), D(0))
        current_dollars = sum((current[m].close * current[m].volume for m in slots), D(0))
        price_change = row.close / current[reference_minute].close - 1
        record.update(cohort='quiet' if daily_baseline <= policy.quiet_max_daily_shares else 'already_active',
                      prior_sessions=len(recent), baseline_sessions=recent,
                      baseline_daily_shares=str(daily_baseline), baseline_window_shares=str(volume_baseline),
                      window_shares=str(current_volume), window_dollar_proxy=str(current_dollars),
                      price_change=str(price_change), first_price=str(current[reference_minute].close),
                      observed_price=str(row.close), relative_volume=None)
        if volume_baseline <= 0:
            record['reasons'] = ['zero_or_sparse_activity_baseline_requires_separate_model']
            decisions.append(record)
            continue
        relative_volume = current_volume / volume_baseline
        record['relative_volume'] = str(relative_volume)
        failures = []
        if price_change < policy.minimum_price_rise:
            failures.append('insufficient_upward_price_movement')
        if relative_volume < policy.minimum_relative_volume:
            failures.append('no_unusual_activity_increase')
        if current_dollars < policy.minimum_window_dollars:
            failures.append('insufficient_absolute_recent_activity')
        if failures:
            record.update(state='observed_no_activation', reasons=failures)
        elif record['cohort'] == 'already_active':
            record.update(state='active_momentum_control', reasons=['not_previously_quiet'])
        elif last_candidate is not None and available_at - last_candidate < policy.cooldown_minutes * 60:
            record.update(state='same_burst_update', reasons=['candidate_already_recorded_for_this_burst'])
        else:
            record.update(state='quiet_to_active_candidate', reasons=['prior_quiet_baseline',
                          'upward_price_movement', 'unusual_activity_increase', 'absolute_activity_observed'])
            record['event_id'] = hashlib.sha256(
                f'{symbol}/{available_at}/{policy.fingerprint()}'.encode()).hexdigest()
            last_candidate = available_at
        decisions.append(record)
    return decisions


def study_gate(universe, series, evaluation_start, evaluation_end, decisions, bar_minutes):
    """Refuse convenience/partial/backdated evidence as a target-cohort study."""
    reasons = []
    symbols = universe.get('symbols', [])
    if universe.get('selection_basis') != 'broad_listing_snapshot' or not universe.get('source_sha256'):
        reasons.append('universe_not_independently_sourced')
    if not symbols or len(set(symbols)) != len(symbols):
        reasons.append('invalid_universe_membership')
    if universe.get('available_at', evaluation_end + 1) > evaluation_start:
        reasons.append('universe_not_available_at_evaluation_start')
    if evaluation_start >= evaluation_end:
        reasons.append('invalid_evaluation_window')
    instrument_types = universe.get('instrument_types', {})
    if any(instrument_types.get(symbol) not in ('stock', 'etf') for symbol in symbols):
        reasons.append('instrument_scope_not_qualified')
    windows = universe.get('session_windows', [])
    valid_windows = bool(windows) and all(
        isinstance(w.get('open'), int) and isinstance(w.get('close'), int) and
        evaluation_start <= w['open'] < w['close'] <= evaluation_end and
        (w['close']-w['open']) % (bar_minutes*60) == 0 for w in windows)
    if not valid_windows:
        reasons.append('exchange_calendar_coverage_not_qualified')
    missing = sorted(set(symbols) - set(series))
    if missing:
        reasons.append('incomplete_declared_universe_coverage')
    unsupported = sorted(set(series) - set(symbols))
    if unsupported:
        reasons.append('undeclared_symbols_in_dataset')
    covered = []
    for symbol in symbols:
        bars = series.get(symbol, [])
        if not bars or not valid_windows:
            continue
        stamps = {b.timestamp for b in bars}
        if any(any(t not in stamps for t in range(w['open'], w['close'], bar_minutes*60)) for w in windows):
            continue
        covered.append(symbol)
    observed = sum(bool(series.get(symbol)) and any(evaluation_start <= b.timestamp < evaluation_end
                   for b in series[symbol]) for symbol in symbols)
    if observed != len(symbols):
        reasons.append('missing_evaluation_window_observations')
    if valid_windows and len(covered) != len(symbols):
        reasons.append('incomplete_evaluation_session_coverage')
    relevant = [r for r in decisions if evaluation_start <= r['available_at'] < evaluation_end]
    quiet = {r['symbol'] for r in relevant if r.get('cohort') == 'quiet'}
    if not quiet:
        reasons.append('no_measured_quiet_stock_evidence')
    return dict(target_study_ready=not reasons, reasons=reasons,
                declared_symbols=len(symbols), observed_symbols=observed,
                qualified_coverage_symbols=len(covered),
                measured_quiet_symbols=len(quiet), missing_symbols=missing,
                performance_validated=False, live_eligible=False)
