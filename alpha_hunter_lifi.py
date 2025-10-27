#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha Hunter - LI.FI版本
使用LI.FI聚合器进行Alpha代币自动交易
聚合所有DEX，获取最优价格
"""

import os
import time
import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('alpha_hunter.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LiFiTrader:
    """LI.FI交易器 - 聚合所有DEX获取最优价格"""
    
    # LI.FI API端点
    LIFI_API = "https://li.quest/v1"
    
    # BNB Chain配置
    BSC_CHAIN_ID = 56
    BSC_RPC = "https://bsc-dataseed1.binance.org"
    WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
    NATIVE_TOKEN = "0x0000000000000000000000000000000000000000"  # BNB
    
    # ERC20 ABI (简化版)
    ERC20_ABI = [
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
        {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    ]
    
    def __init__(self, private_key: str, rpc_url: str = None):
        """初始化LI.FI交易器"""
        logger.info("=" * 60)
        logger.info("[BOT] Alpha Hunter - LI.FI版")
        logger.info("[INFO] 聚合所有DEX，获取最优价格")
        logger.info("=" * 60)
        
        self.private_key = private_key
        self.rpc_url = rpc_url or self.BSC_RPC
        
        # 初始化Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not self.w3.is_connected():
            raise ConnectionError(f"无法连接到BSC节点: {self.rpc_url}")
        
        # 创建账户
        self.account = Account.from_key(private_key)
        self.wallet_address = self.account.address
        
        logger.info(f"[OK] LI.FI交易器初始化成功")
        logger.info(f"[ADDR] 钱包地址: {self.wallet_address}")
        logger.info(f"[LINK] LI.FI API: {self.LIFI_API}")
        logger.info(f"[LINK] BSC RPC: {self.rpc_url}")
    
    def get_bnb_balance(self) -> float:
        """获取BNB余额"""
        try:
            balance_wei = self.w3.eth.get_balance(self.wallet_address)
            return float(self.w3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            logger.error(f"[ERROR] 获取BNB余额失败: {e}")
            return 0.0
    
    def get_token_balance(self, token_address: str) -> float:
        """获取代币余额"""
        try:
            token = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self.ERC20_ABI
            )
            balance = token.functions.balanceOf(self.wallet_address).call()
            decimals = token.functions.decimals().call()
            return balance / (10 ** decimals)
        except Exception as e:
            logger.error(f"[ERROR] 获取代币余额失败: {e}")
            return 0.0
    
    def get_quote(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        slippage: float = 0.01,
        max_retries: int = 3
    ) -> Optional[Dict]:
        """获取LI.FI报价（带重试机制）"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = attempt * 3  # 3秒、6秒递增
                    logger.info(f"[RETRY] 等待 {wait_time}秒后重试...")
                    time.sleep(wait_time)
                
                logger.info(f"[QUOTE] 通过LI.FI获取最优报价...")
                
                params = {
                    'fromChain': str(self.BSC_CHAIN_ID),
                    'toChain': str(self.BSC_CHAIN_ID),
                    'fromToken': from_token,
                    'toToken': to_token,
                    'fromAmount': str(int(amount * 10**18)),
                    'fromAddress': self.wallet_address,
                    'slippage': slippage
                }
                
                url = f"{self.LIFI_API}/quote"
                response = requests.get(url, params=params, timeout=30)
                
                # 处理429错误（限流）
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        logger.warning(f"[WARN] API限流，等待后重试 ({attempt+1}/{max_retries})")
                        continue
                    else:
                        logger.error(f"[ERROR] API限流，已达最大重试次数")
                        return None
                
                response.raise_for_status()
                
                quote = response.json()
                
                if 'estimate' in quote:
                    estimate = quote['estimate']
                    to_amount = float(estimate['toAmount']) / 10**18
                    
                    logger.info(f"[OK] 报价成功!")
                    logger.info(f"[RECEIVE] 预计获得: {to_amount:.6f} 代币")
                    
                    # 显示使用的DEX
                    if 'includedSteps' in quote:
                        for step in quote['includedSteps']:
                            tool = step.get('toolDetails', {}).get('name', 'Unknown')
                            logger.info(f"[DEX] 通过: {tool}")
                    
                    return quote
                else:
                    logger.error(f"[ERROR] 报价失败")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    logger.warning(f"[WARN] API限流，等待后重试 ({attempt+1}/{max_retries})")
                    continue
                else:
                    logger.error(f"[ERROR] 获取报价失败: {e}")
                    return None
            except Exception as e:
                logger.error(f"[ERROR] 获取报价失败: {e}")
                if attempt < max_retries - 1:
                    continue
                return None
        
        return None
    
    def buy_token(
        self,
        token_address: str,
        amount_in_bnb: float,
        slippage: float = 0.1,
        wait_for_liquidity: bool = False,
        retry_interval: int = 30
    ) -> Optional[str]:
        """
        使用LI.FI买入代币
        
        Args:
            token_address: 代币地址
            amount_in_bnb: BNB投入金额
            slippage: 滑点容忍度
            wait_for_liquidity: 是否等待流动性出现
            retry_interval: 重试间隔（秒）
            
        Returns:
            交易哈希或None
        """
        try:
            logger.info(f"[->] 准备买入代币...")
            logger.info(f"[TOKEN] 代币地址: {token_address}")
            logger.info(f"[BNB] 投入: {amount_in_bnb} BNB")
            logger.info(f"[DATA] 滑点: {slippage*100}%")
            logger.info(f"[LIFI] 使用LI.FI聚合器")
            
            # 检查余额
            balance = self.get_bnb_balance()
            if balance < amount_in_bnb:
                logger.error(f"[ERROR] BNB余额不足: {balance} < {amount_in_bnb}")
                return None
            
            # 1. 获取报价（循环等待模式）
            quote = None
            retry_count = 0
            
            while True:
                retry_count += 1
                
                if retry_count > 1:
                    logger.info(f"[RETRY] 第 {retry_count} 次尝试...")
                
                quote = self.get_quote(
                    from_token=self.NATIVE_TOKEN,
                    to_token=token_address,
                    amount=amount_in_bnb,
                    slippage=slippage
                )
                
                if quote:
                    # 获取到报价，跳出循环
                    break
                
                if not wait_for_liquidity:
                    # 不等待流动性，直接返回失败
                    logger.error("[FAILED] 无法获取报价，退出")
                    return None
                
                # 等待流动性模式
                logger.warning(f"[WAIT] 未检测到流动性池，等待 {retry_interval}秒后重试...")
                logger.info(f"[TIP] 按 Ctrl+C 可随时停止等待")
                
                try:
                    time.sleep(retry_interval)
                except KeyboardInterrupt:
                    logger.info("\n[CANCEL] 用户取消等待")
                    return None
            
            if not quote:
                return None
            
            # 2. 获取交易数据
            transaction_request = quote.get('transactionRequest')
            if not transaction_request:
                logger.error("[ERROR] 无法获取交易数据")
                return None
            
            # 3. 构建交易
            tx = {
                'from': Web3.to_checksum_address(self.wallet_address),
                'to': Web3.to_checksum_address(transaction_request['to']),
                'value': int(transaction_request.get('value', '0'), 16),
                'data': transaction_request['data'],
                'gas': int(transaction_request.get('gasLimit', '500000'), 16),
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address),
                'chainId': self.BSC_CHAIN_ID
            }
            
            # 4. 签名交易
            logger.info("[SIGN] 签名交易...")
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            
            # 5. 发送交易
            logger.info("[SEND] 发送交易...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"[SEND] 交易已发送: {tx_hash_hex}")
            logger.info(f"[SCAN] https://bscscan.com/tx/{tx_hash_hex}")
            
            # 6. 等待确认
            logger.info("[WAIT] 等待交易确认...")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                logger.info(f"[OK] 买入成功! Gas: {receipt['gasUsed']}")
                return tx_hash_hex
            else:
                logger.error(f"[FAILED] 交易失败!")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] 买入失败: {e}")
            return None
    
    def sell_token(
        self,
        token_address: str,
        amount: float,
        slippage: float = 0.1
    ) -> Optional[str]:
        """使用LI.FI卖出代币"""
        try:
            logger.info(f"[->] 准备卖出代币...")
            logger.info(f"[TOKEN] 代币地址: {token_address}")
            logger.info(f"[DATA] 数量: {amount}")
            logger.info(f"[LIFI] 使用LI.FI聚合器")
            
            # 检查余额
            balance = self.get_token_balance(token_address)
            if balance < amount:
                logger.error(f"[ERROR] 代币余额不足: {balance} < {amount}")
                return None
            
            # 1. 获取报价
            quote = self.get_quote(
                from_token=token_address,
                to_token=self.NATIVE_TOKEN,  # 卖成BNB
                amount=amount,
                slippage=slippage
            )
            
            if not quote:
                return None
            
            # 2. 获取交易数据
            transaction_request = quote.get('transactionRequest')
            if not transaction_request:
                logger.error("[ERROR] 无法获取交易数据")
                return None
            
            # 3. 构建交易
            tx = {
                'from': Web3.to_checksum_address(self.wallet_address),
                'to': Web3.to_checksum_address(transaction_request['to']),
                'value': int(transaction_request.get('value', '0'), 16),
                'data': transaction_request['data'],
                'gas': int(transaction_request.get('gasLimit', '500000'), 16),
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address),
                'chainId': self.BSC_CHAIN_ID
            }
            
            # 4. 签名并发送
            logger.info("[SIGN] 签名交易...")
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            
            logger.info("[SEND] 发送交易...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"[SEND] 交易已发送: {tx_hash_hex}")
            logger.info(f"[SCAN] https://bscscan.com/tx/{tx_hash_hex}")
            
            # 5. 等待确认
            logger.info("[WAIT] 等待交易确认...")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                logger.info(f"[OK] 卖出成功! Gas: {receipt['gasUsed']}")
                return tx_hash_hex
            else:
                logger.error(f"[FAILED] 交易失败!")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] 卖出失败: {e}")
            return None


class AlphaHunter:
    """Alpha Hunter - 使用LI.FI聚合器的自动交易机器人"""
    
    def __init__(self, private_key: str):
        """初始化Alpha Hunter"""
        logger.info("=" * 60)
        logger.info("[BOT] Alpha Hunter - LI.FI版")
        logger.info("[INFO] 聚合所有DEX，自动止盈")
        logger.info("=" * 60)
        
        # 初始化LI.FI交易器
        rpc_url = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed1.binance.org')
        self.trader = LiFiTrader(private_key, rpc_url)
        
        # 加载配置
        self.initial_investment = float(os.getenv('INITIAL_INVESTMENT', '0.05'))
        self.slippage = float(os.getenv('SLIPPAGE', '0.15'))
        self.max_positions = int(os.getenv('MAX_POSITIONS', '5'))
        
        # 持仓记录
        self.positions: Dict[str, Dict] = {}
        
        # 止盈策略
        self.profit_targets = [
            {'multiplier': 2.0, 'sell_percent': 0.5, 'description': '2倍出本金'},
            {'multiplier': 3.0, 'sell_percent': 0.1, 'description': '3倍出10%'},
            {'multiplier': 5.0, 'sell_percent': 0.2, 'description': '5倍出20%'},
            {'multiplier': 10.0, 'sell_percent': 0.2, 'description': '10倍出20%'}
        ]
        
        logger.info("[CFG] 配置信息:")
        logger.info(f"  [BNB] 每次投资: {self.initial_investment} BNB")
        logger.info(f"  [DATA] 滑点容忍: {self.slippage*100}%")
        logger.info(f"  [BOX] 最大持仓: {self.max_positions}")
        logger.info("[TARGET] 止盈策略:")
        for target in self.profit_targets:
            logger.info(f"  {target['description']}")
        logger.info("=" * 60)
    
    def hunt_alpha_token(self, token_info: Dict, wait_for_liquidity: bool = False, retry_interval: int = 30):
        """
        猎杀Alpha代币
        
        Args:
            token_info: 代币信息字典
            wait_for_liquidity: 是否循环等待流动性出现
            retry_interval: 重试间隔（秒）
        """
        symbol = token_info.get('symbol')
        token_address = token_info.get('address')
        
        if not token_address:
            logger.error("[ERROR] 代币地址为空")
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info(f"[TARGET] 开始猎杀Alpha代币: {symbol}")
        logger.info("=" * 60)
        
        if wait_for_liquidity:
            logger.info(f"[MODE] 循环等待模式")
            logger.info(f"[INTERVAL] 检测间隔: {retry_interval}秒")
        
        # 执行买入
        tx_hash = self.trader.buy_token(
            token_address=token_address,
            amount_in_bnb=self.initial_investment,
            slippage=self.slippage,
            wait_for_liquidity=wait_for_liquidity,
            retry_interval=retry_interval
        )
        
        if not tx_hash:
            logger.error("[FAILED] 买入失败")
            return False
        
        # 记录持仓
        initial_balance = self.trader.get_token_balance(token_address)
        self.positions[symbol] = {
            'address': token_address,
            'initial_balance': initial_balance,
            'current_balance': initial_balance,
            'buy_tx': tx_hash,
            'buy_time': datetime.now().isoformat(),
            'investment_bnb': self.initial_investment,
            'sold_history': []
        }
        
        self.save_positions()
        logger.info(f"[POSITION] 持仓已记录: {symbol}")
        logger.info(f"[BALANCE] 初始余额: {initial_balance:.6f}")
        
        return True
    
    def get_token_value_in_bnb(self, token_address: str, token_amount: float) -> Optional[float]:
        """
        获取代币的BNB价值（通过LI.FI查询）
        
        Args:
            token_address: 代币地址
            token_amount: 代币数量
            
        Returns:
            BNB价值
        """
        try:
            # 通过LI.FI获取报价（卖成BNB能得到多少）
            quote = self.trader.get_quote(
                from_token=token_address,
                to_token=self.trader.NATIVE_TOKEN,
                amount=token_amount,
                slippage=self.slippage
            )
            
            if quote and 'estimate' in quote:
                bnb_amount = float(quote['estimate']['toAmount']) / 10**18
                return bnb_amount
            
            return None
            
        except Exception as e:
            logger.error(f"[ERROR] 查询代币价值失败: {e}")
            return None
    
    def check_and_sell(self):
        """检查并执行止盈（基于法币价值）"""
        if not self.positions:
            return
        
        logger.info(f"\n[CHECK] 检查持仓 ({len(self.positions)}个)...")
        
        for symbol, pos in list(self.positions.items()):
            try:
                token_address = pos['address']
                current_balance = self.trader.get_token_balance(token_address)
                
                if current_balance == 0:
                    logger.info(f"  {symbol}: 已全部卖出，移除持仓")
                    del self.positions[symbol]
                    continue
                
                # 更新当前余额
                pos['current_balance'] = current_balance
                
                # 获取当前持仓的BNB价值
                logger.info(f"  {symbol}: 查询当前价值...")
                current_bnb_value = self.get_token_value_in_bnb(token_address, current_balance)
                
                if current_bnb_value is None:
                    logger.warning(f"  {symbol}: 无法获取价值，跳过")
                    time.sleep(2)  # API限流保护
                    continue
                
                # 计算基于法币的收益倍数
                investment_bnb = pos.get('investment_bnb', 0.05)
                profit_mult = current_bnb_value / investment_bnb if investment_bnb > 0 else 1.0
                
                logger.info(f"  {symbol}: {current_balance:.6f} 代币")
                logger.info(f"  投入: {investment_bnb:.4f} BNB | 当前: {current_bnb_value:.4f} BNB | 倍数: {profit_mult:.2f}x")
                
                # 找到应该执行的最高止盈点（只执行一个，避免API限流）
                executed_multipliers = set(h.get('multiplier') for h in pos.get('sold_history', []))
                
                target_to_execute = None
                for target in reversed(self.profit_targets):  # 从高到低检查
                    if profit_mult >= target['multiplier'] and target['multiplier'] not in executed_multipliers:
                        target_to_execute = target
                        break
                
                if target_to_execute:
                    # 执行止盈
                    sell_amount = current_balance * target_to_execute['sell_percent']
                    logger.info(f"\n[PROFIT] {symbol} 达到 {target_to_execute['multiplier']}x!")
                    logger.info(f"[SELL] 执行止盈: 卖出 {sell_amount:.6f} 代币 ({target_to_execute['sell_percent']*100}%)")
                    
                    # 添加延迟避免API限流
                    time.sleep(2)
                    
                    tx_hash = self.trader.sell_token(
                        token_address=token_address,
                        amount=sell_amount,
                        slippage=self.slippage
                    )
                    
                    if tx_hash:
                        # 记录卖出历史
                        pos.setdefault('sold_history', []).append({
                            'multiplier': target_to_execute['multiplier'],
                            'amount': sell_amount,
                            'tx': tx_hash,
                            'time': datetime.now().isoformat(),
                            'bnb_value': current_bnb_value,
                            'profit_mult': profit_mult
                        })
                        logger.info(f"[OK] 止盈完成: {target_to_execute['description']}")
                        
                        # 成功后再次延迟
                        time.sleep(3)
                    else:
                        logger.error(f"[FAILED] 止盈失败")
                        # 失败也要延迟，避免API限流
                        time.sleep(5)
                
            except Exception as e:
                logger.error(f"[ERROR] 检查 {symbol} 失败: {e}")
                time.sleep(2)  # 错误后也延迟
        
        self.save_positions()
    
    def save_positions(self):
        """保存持仓数据"""
        try:
            with open('positions.json', 'w', encoding='utf-8') as f:
                json.dump(self.positions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[ERROR] 保存持仓失败: {e}")
    
    def load_positions(self):
        """加载持仓数据"""
        try:
            if os.path.exists('positions.json'):
                with open('positions.json', 'r', encoding='utf-8') as f:
                    self.positions = json.load(f)
                logger.info(f"[LOAD] 加载了 {len(self.positions)} 个持仓")
        except Exception as e:
            logger.error(f"[ERROR] 加载持仓失败: {e}")
            self.positions = {}
    
    def run_monitor(self, check_interval: int = 30):
        """运行监控"""
        self.load_positions()
        
        logger.info("\n" + "=" * 60)
        logger.info("[START] 持仓监控已启动")
        logger.info("=" * 60)
        logger.info(f"⏱️  检查间隔: {check_interval}秒")
        logger.info(f"[INFO] 当前持仓: {len(self.positions)} 个")
        logger.info("\n按 Ctrl+C 停止运行\n")
        
        if not self.positions:
            logger.warning("[WARN] 当前无持仓，无需监控")
            logger.info("[TIP] 请先买入代币再启动监控")
            return
        
        try:
            last_check_time = 0
            
            while True:
                current_time = time.time()
                
                # 检查持仓止盈
                if current_time - last_check_time >= check_interval:
                    if self.positions:
                        logger.info(f"\n{'='*60}")
                        logger.info(f"[CHECK] 检查持仓止盈...")
                        logger.info(f"{'='*60}")
                        self.check_and_sell()
                        last_check_time = current_time
                    else:
                        logger.info("\n[INFO] 所有持仓已清空，停止监控")
                        break
                
                # 短暂休息
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("\n\n[STOP] 收到停止信号")
            logger.info("[SAVE] 保存持仓数据...")
            self.save_positions()
            logger.info("[BYE] Alpha Hunter 已停止")


if __name__ == '__main__':
    print("=" * 60)
    print("Alpha Hunter - LI.FI版")
    print("=" * 60)
    print("\n请使用 auto_trade.py 启动程序")
    print("或运行 python test_lifi.py 测试LI.FI连接\n")
    print("=" * 60)

