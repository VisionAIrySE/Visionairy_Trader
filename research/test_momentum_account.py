import unittest
from momentum_holdout_account import simulate

def trade(symbol,start=1,end=2,ret=0,date='2025-04-01'):
    return dict(symbol=symbol,entry_at=start,exit_at=end,entry_price=10,initial_risk=.02,return_=ret,date=date,**{'return':ret})

class AccountTests(unittest.TestCase):
    def test_cash_cannot_recycle_same_day(self):
        rows=[trade(str(i),i*3+1,i*3+2) for i in range(11)]
        self.assertEqual(simulate(rows)['trades'],10)
    def test_loss_reduces_account(self):
        self.assertAlmostEqual(simulate([trade('X',ret=-.1)])['final_value'],990)
    def test_proceeds_available_next_date(self):
        rows=[trade(str(i),i*3+1,i*3+2) for i in range(10)]+[trade('NEXT',40,41,date='2025-04-02')]
        self.assertEqual(simulate(rows)['trades'],11)
    def test_duplicate_position_excluded(self):
        self.assertEqual(simulate([trade('X',1,5),trade('X',2,6)])['trades'],1)

if __name__=='__main__':unittest.main()
