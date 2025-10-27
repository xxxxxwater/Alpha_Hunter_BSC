#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha Hunter - LI.FI版本 v2.9
使用LI.FI聚合器进行Alpha代币自动交易
v2.9: 强化API限流保护，指数退避，请求缓存
"""

import os
import time
import json
import logging
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from collections import deque

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

# 版本信息
VERSION = "2.9.0"


class AdvancedRateLimiter:
    """高级API限流器 - 滑动窗口算法 + 指数退避"""
    
    def __init__(self, 
                 requests_per_minute: int = 10,
                 requests_per_hour: int = 100,
                 enable_exponential_backoff: bool = True):
        """
        初始化高级限流器
        
        Args:
            requests_per_minute: 每分钟最大请求数
            requests_per_hour: 每小时最大请求数
            enable_exponential_backoff: 启用指数退避
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.enable_exponential_backoff = enable_exponential_backoff
        
        # 使用滑动窗口记录请求时间
        self.minute_window = deque(maxlen=requests_per_minute)
        self.hour_window = deque(maxlen=requests_per_hour)
        
        # 指数退避
        self.consecutive_failures = 0
        self.last_failure_time = None
        
        # 线程锁
        self.lock = threading.Lock()
        
        logger.info(f"[LIMITER] 高级限流器初始化")
        logger.info(f"[LIMITER] 限制: {requests_per_minute}req/min, {requests_per_hour}req/hour")
        if enable_exponential_backoff:
            logger.info(f"[LIMITER] 指数退避: 已启用")
    
    def wait_if_needed(self):
        """智能等待 - 滑动窗口 + 指数退避"""
        with self.lock:
            now = time.time()
            
            # 1. 检查指数退避
            if self.enable_exponential_backoff and self.consecutive_failures > 0:
                backoff_time = min(60, 2 ** self.consecutive_failures)  # 最多等待60秒
                if self.last_failure_time:
                    elapsed = now - self.last_failure_time
                    if elapsed < backoff_time:
                        wait_time = backoff_time - elapsed
                        logger.warning(f"[BACKOFF] 指数退避: 等待 {wait_time:.1f}秒 (失败{self.consecutive_failures}次)")
                        time.sleep(wait_time)
                        now = time.time()
            
            # 2. 清理过期的请求记录（超过1分钟）
            cutoff_minute = now - 60
            while self.minute_window and self.minute_window[0] < cutoff_minute:
                self.minute_window.popleft()
            
            # 3. 清理过期的请求记录（超过1小时）
            cutoff_hour = now - 3600
            while self.hour_window and self.hour_window[0] < cutoff_hour:
                self.hour_window.popleft()
            
            # 4. 检查分钟级限流
            if len(self.minute_window) >= self.requests_per_minute:
                oldest = self.minute_window[0]
                wait_time = 60 - (now - oldest) + 1
                if wait_time > 0:
                    logger.warning(f"[LIMIT-MIN] 达到分钟限流，等待 {wait_time:.1f}秒...")
                    time.sleep(wait_time)
                    now = time.time()
                    # 重新清理
                    cutoff_minute = now - 60
                    while self.minute_window and self.minute_window[0] < cutoff_minute:
                        self.minute_window.popleft()
            
            # 5. 检查小时级限流
            if len(self.hour_window) >= self.requests_per_hour:
                oldest = self.hour_window[0]
                wait_time = 3600 - (now - oldest) + 1
                if wait_time > 0:
                    logger.warning(f"[LIMIT-HOUR] 达到小时限流，等待 {wait_time:.1f}秒...")
                    time.sleep(wait_time)
                    now = time.time()
            
            # 6. 记录本次请求
            self.minute_window.append(now)
            self.hour_window.append(now)
    
    def record_success(self):
        """记录成功请求，重置退避计数器"""
        with self.lock:
            if self.consecutive_failures > 0:
                logger.info(f"[BACKOFF] 请求成功，重置退避计数器")
            self.consecutive_failures = 0
            self.last_failure_time = None
    
    def record_failure(self):
        """记录失败请求，增加退避计数器"""
        with self.lock:
            self.consecutive_failures += 1
            self.last_failure_time = time.time()
            if self.consecutive_failures > 1:
                backoff_time = min(60, 2 ** self.consecutive_failures)
                logger.warning(f"[BACKOFF] 连续失败{self.consecutive_failures}次，下次等待{backoff_time}秒")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            return {
                'minute_requests': len(self.minute_window),
                'hour_requests': len(self.hour_window),
                'consecutive_failures': self.consecutive_failures,
                'minute_limit': self.requests_per_minute,
                'hour_limit': self.requests_per_hour
            }


class QuoteCache:
    """报价缓存 - 减少API请求"""
    
    def __init__(self, cache_duration: int = 10):
        """
        初始化缓存
        
        Args:
            cache_duration: 缓存持续时间（秒）
        """
        self.cache = {}
        self.cache_duration = cache_duration
        self.lock = threading.Lock()
        logger.info(f"[CACHE] 报价缓存初始化，有效期: {cache_duration}秒")
    
    def get(self, key: str) -> Optional[Dict]:
        """获取缓存"""
        with self.lock:
            if key in self.cache:
                data, timestamp = self.cache[key]
                if time.time() - timestamp < self.cache_duration:
                    logger.info(f"[CACHE] 命中缓存: {key}")
                    return data
                else:
                    del self.cache[key]
            return None
    
    def set(self, key: str, value: Dict):
        """设置缓存"""
        with self.lock:
            self.cache[key] = (value, time.time())
            logger.debug(f"[CACHE] 缓存报价: {key}")
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            logger.info(f"[CACHE] 缓存已清空")


class LiFiTrader:
    """LI.FI交易器 - v2.9 强化限流版"""
    
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
        """初始化LI.FI交易器 v2.9"""
        logger.info("=" * 60)
        logger.info(f"[BOT] Alpha Hunter - LI.FI版 v{VERSION}")
        logger.info("[INFO] 聚合所有DEX，强化限流保护")
        logger.info("=" * 60)
        
        self.private_key = private_key
        self.rpc_url = rpc_url or self.BSC_RPC
        
        # LI.FI API密钥（可选）
        self.lifi_api_key = os.getenv('LIFI_API_KEY', '')
        
        # 初始化高级限流器
        requests_per_minute = int(os.getenv('API_REQUESTS_PER_MINUTE', '8'))  # 更保守
        requests_per_hour = int(os.getenv('API_REQUESTS_PER_HOUR', '80'))
        self.rate_limiter = AdvancedRateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            enable_exponential_backoff=True
        )
        
        # 初始化报价缓存
        cache_duration = int(os.getenv('QUOTE_CACHE_DURATION', '15'))  # 15秒缓存
        self.quote_cache = QuoteCache(cache_duration=cache_duration)
        
        # 初始化Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not self.w3.is_connected():
            raise ConnectionError(f"无法连接到BSC节点: {self.rpc_url}")
        
        # 创建账户
        self.account = Account.from_key(private_key)
        self.wallet_address = self.account.address
        
        logger.info(f"[OK] LI.FI交易器 v{VERSION} 初始化成功")
        logger.info(f"[ADDR] 钱包地址: {self.wallet_address}")
        logger.info(f"[LINK] LI.FI API: {self.LIFI_API}")
        logger.info(f"[LINK] BSC RPC: {self.rpc_url}")
        if self.lifi_api_key:
            logger.info(f"[KEY] LI.FI API密钥: 已配置")
    
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
        max_retries: int = 5,  # 增加重试次数
        use_cache: bool = True
    ) -> Optional[Dict]:
        """
        获取LI.FI报价 v2.9 - 强化限流版
        
        Args:
            from_token: 源代币地址
            to_token: 目标代币地址
            amount: 数量
            slippage: 滑点
            max_retries: 最大重试次数
            use_cache: 是否使用缓存
            
        Returns:
            报价信息或None
        """
        # 生成缓存键
        cache_key = f"{from_token}_{to_token}_{amount}_{slippage}"
        
        # 尝试从缓存获取
        if use_cache:
            cached_quote = self.quote_cache.get(cache_key)
            if cached_quote:
                return cached_quote
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # 指数退避：2, 4, 8, 16, 32秒
                    wait_time = min(60, 2 ** attempt)
                    logger.info(f"[RETRY] 重试 {attempt}/{max_retries}，等待 {wait_time}秒...")
                    time.sleep(wait_time)
                
                # 全局限流等待
                self.rate_limiter.wait_if_needed()
                
                logger.info(f"[QUOTE] 通过LI.FI获取报价 (尝试{attempt+1}/{max_retries})...")
                
                params = {
                    'fromChain': str(self.BSC_CHAIN_ID),
                    'toChain': str(self.BSC_CHAIN_ID),
                    'fromToken': from_token,
                    'toToken': to_token,
                    'fromAmount': str(int(amount * 10**18)),
                    'fromAddress': self.wallet_address,
                    'slippage': slippage
                }
                
                headers = {}
                if self.lifi_api_key:
                    headers['x-lifi-api-key'] = self.lifi_api_key
                
                url = f"{self.LIFI_API}/quote"
                response = requests.get(url, params=params, headers=headers, timeout=30)
                
                # 处理429错误（限流）
                if response.status_code == 429:
                    logger.warning(f"[WARN] API限流 (429)")
                    self.rate_limiter.record_failure()
                    if attempt < max_retries - 1:
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
                    
                    # 记录成功
                    self.rate_limiter.record_success()
                    
                    # 缓存报价
                    if use_cache:
                        self.quote_cache.set(cache_key, quote)
                    
                    # 显示限流器统计
                    stats = self.rate_limiter.get_stats()
                    logger.info(f"[STATS] API使用: 分钟{stats['minute_requests']}/{stats['minute_limit']}, "
                              f"小时{stats['hour_requests']}/{stats['hour_limit']}")
                    
                    return quote
                else:
                    logger.error(f"[ERROR] 报价响应无效")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logger.warning(f"[WARN] API限流 (429)")
                    self.rate_limiter.record_failure()
                    if attempt < max_retries - 1:
                        continue
                else:
                    logger.error(f"[ERROR] HTTP错误: {e}")
                    self.rate_limiter.record_failure()
                    if attempt < max_retries - 1:
                        continue
                return None
            except Exception as e:
                logger.error(f"[ERROR] 获取报价失败: {e}")
                self.rate_limiter.record_failure()
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
        使用LI.FI买入代币 v2.9
        
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
            logger.info(f"[LIFI] 使用LI.FI聚合器 v{VERSION}")
            
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
                    slippage=slippage,
                    use_cache=False  # 买入时不使用缓存
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
        """使用LI.FI卖出代币 v2.9"""
        try:
            logger.info(f"[->] 准备卖出代币...")
            logger.info(f"[TOKEN] 代币地址: {token_address}")
            logger.info(f"[DATA] 数量: {amount}")
            logger.info(f"[LIFI] 使用LI.FI聚合器 v{VERSION}")
            
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
                slippage=slippage,
                use_cache=False  # 卖出时不使用缓存
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
    """Alpha Hunter - 使用LI.FI聚合器的自动交易机器人 v2.9"""
    
    def __init__(self, private_key: str):
        """初始化Alpha Hunter v2.9"""
        logger.info("=" * 60)
        logger.info(f"[BOT] Alpha Hunter - LI.FI版 v{VERSION}")
        logger.info("[INFO] 聚合所有DEX，智能限流，自动止盈")
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
        猎杀Alpha代币 v2.9
        
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
            logger.info(f"[MODE] 循环等待模式 (v{VERSION})")
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
        获取代币的BNB价值（通过LI.FI查询）v2.9
        
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
                slippage=self.slippage,
                use_cache=True  # 查询价值时使用缓存
            )
            
            if quote and 'estimate' in quote:
                bnb_amount = float(quote['estimate']['toAmount']) / 10**18
                return bnb_amount
            
            return None
            
        except Exception as e:
            logger.error(f"[ERROR] 查询代币价值失败: {e}")
            return None
    
    def check_and_sell(self):
        """检查并执行止盈（基于法币价值）v2.9"""
        if not self.positions:
            return
        
        logger.info(f"\n[CHECK] 检查持仓 ({len(self.positions)}个) - v{VERSION}...")
        
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
                    logger.warning(f"  {symbol}: 无法获取价值，跳过本次检查")
                    # 即使获取失败，也不要立即重试，等待下次检查
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
                    time.sleep(3)
                    
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
                        time.sleep(5)
                    else:
                        logger.error(f"[FAILED] 止盈失败")
                        # 失败也要延迟，避免API限流
                        time.sleep(10)
                else:
                    # 未达到止盈条件，添加小延迟
                    time.sleep(2)
                
            except Exception as e:
                logger.error(f"[ERROR] 检查 {symbol} 失败: {e}")
                time.sleep(3)  # 错误后也延迟
        
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
    
    def run_monitor(self, check_interval: int = 60):  # 默认60秒，更保守
        """
        运行监控 v2.9
        
        Args:
            check_interval: 检查间隔（秒），建议不低于60秒
        """
        self.load_positions()
        
        logger.info("\n" + "=" * 60)
        logger.info(f"[START] 持仓监控已启动 (v{VERSION})")
        logger.info("=" * 60)
        logger.info(f"⏱️  检查间隔: {check_interval}秒")
        logger.info(f"[INFO] 当前持仓: {len(self.positions)} 个")
        logger.info(f"[TIP] 建议检查间隔不低于60秒，避免API限流")
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
            logger.info(f"[BYE] Alpha Hunter v{VERSION} 已停止")


if __name__ == '__main__':
    print("=" * 60)
    print(f"Alpha Hunter - LI.FI版 v{VERSION}")
    print("=" * 60)
    print("\n请使用 auto_trade_lifi.py 启动程序")
    print("或运行 python test_lifi.py 测试LI.FI连接\n")
    print("=" * 60)

