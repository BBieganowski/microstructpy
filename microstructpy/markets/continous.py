from microstructpy.markets.base import Market
from microstructpy.orders.market import MarketOrder
import random


class ContinousOrderBookMarket(Market):
    def __init__(self):
        super().__init__()
        self.bid_ob = []
        self.ask_ob = []
        self.ob_snapshots = []
        self.midprices = [(0, 0)]

    def submit_order(self, order):
        if isinstance(order, MarketOrder):
            if order.quantity > 0 and self.ask_ob == []:
                order.status = "rejected"
                return None
            elif order.quantity < 0 and self.bid_ob == []:
                order.status = "rejected"
                return None
        
        self.last_submission_time += 1
        order.time = self.last_submission_time

        if order.quantity > 0:
            self.bid_ob.append(order)
        else:
            self.ask_ob.append(order)
        order.status = "active"
        submitting_trader = [participant for participant in self.participants if participant.trader_id == order.trader_id][0]
        submitting_trader.orders.append(order)
        self.match_orders()
        self.save_ob_state()

    def save_ob_state(self):
        # Aggregate orders at the same price level
        bid_prices = set([order.price for order in self.bid_ob])
        bid_prices = sorted(bid_prices, reverse=True)
        ask_prices = set([order.price for order in self.ask_ob])
        bid_volumes = [sum([order.quantity for order in self.bid_ob if order.price == price]) for price in bid_prices]
        ask_volumes = [sum([order.quantity for order in self.ask_ob if order.price == price]) for price in ask_prices]
        bid_ob_snapshot = [{"price": price, "volume": volume} for price, volume in zip(bid_prices, bid_volumes)]
        ask_ob_snapshot = [{"price": price, "volume": volume} for price, volume in zip(ask_prices, ask_volumes)]
        self.ob_snapshots.append({"bid": bid_ob_snapshot, "ask": ask_ob_snapshot, 'time': self.last_submission_time})
        if bid_ob_snapshot and ask_ob_snapshot:
            self.midprices.append((self.last_submission_time, (bid_ob_snapshot[0]['price'] + ask_ob_snapshot[0]['price']) / 2))
        else:
            self.midprices.append((self.last_submission_time, 0))

        
    def match_orders(self):
        self.bid_ob.sort(key=lambda x: x.price, reverse=True)
        self.ask_ob.sort(key=lambda x: x.price)
        
        while self.bid_ob and self.ask_ob and self.bid_ob[0].price >= self.ask_ob[0].price:
            bid_order = self.bid_ob[0]
            ask_order = self.ask_ob[0]
            
            fill_price = bid_order.price if bid_order.time < ask_order.time else ask_order.price
            fill_volume = min(bid_order.quantity, abs(ask_order.quantity))
            aggressor_side = 1 if bid_order.time < ask_order.time else -1
            
            buyer = self.get_participant(bid_order.trader_id)
            seller = self.get_participant(ask_order.trader_id)
            
            self.execute_trade(buyer, seller, fill_price, fill_volume, aggressor_side)
            
            bid_order.quantity -= fill_volume
            ask_order.quantity += fill_volume
            
            self.update_order_status(bid_order)
            self.update_order_status(ask_order)
            
            if bid_order.quantity == 0:
                self.bid_ob.pop(0)
            if ask_order.quantity == 0:
                self.ask_ob.pop(0) 

    def get_participant(self, trader_id):
        return next(p for p in self.participants if p.trader_id == trader_id)

    def execute_trade(self, buyer, seller, price, volume, aggressor_side):
        buyer.position += volume
        seller.position -= volume
        
        trade_info = {
            "price": price,
            "volume": volume,
            "aggressor_side": aggressor_side,
            "time": self.last_submission_time
        }
        
        buyer_trade = trade_info.copy()
        buyer_trade["volume"] = volume
        buyer.filled_trades.append(buyer_trade)

        seller_trade = trade_info.copy()
        seller_trade["volume"] = -volume
        seller.filled_trades.append(seller_trade)

        self.trade_history.append(trade_info)

    def update_order_status(self, order):
        if order.quantity == 0:
            order.status = "filled"
        else:
            order.status = "partial"

    def run(self, ticks=10):
        for tick in range(ticks):
            random.shuffle(self.participants)
            for participant in self.participants:
                participant.update()
        self.completed = True 