#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BSC RPC连接测试工具
用于测试各个RPC节点的连接状态和速度
"""

import time
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv
import os

load_dotenv()

# RPC节点列表
BSC_RPCS = [
    "https://bsc-dataseed.binance.org",
    "https://bsc-dataseed1.defibit.io",
    "https://bsc-dataseed1.ninicoin.io",
    "https://bsc.publicnode.com",
    "https://bsc-rpc.publicnode.com",
    "https://binance.nodereal.io"
]

def test_rpc(rpc_url, timeout=10):
    """测试单个RPC节点"""
    try:
        start_time = time.time()
        
        # 创建Web3连接
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': timeout}))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # 检查连接
        if not w3.is_connected():
            return False, 0, "连接失败"
        
        # 测试获取区块号
        block_number = w3.eth.block_number
        
        # 计算延迟
        latency = (time.time() - start_time) * 1000  # 转为毫秒
        
        return True, latency, f"区块高度: {block_number:,}"
        
    except Exception as e:
        return False, 0, str(e)[:50]

def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("BSC RPC 连接测试工具")
    print("=" * 80 + "\n")
    
    # 检查环境变量中的自定义RPC
    custom_rpc = os.getenv('BSC_RPC_URL')
    if custom_rpc:
        print(f"检测到自定义RPC: {custom_rpc}")
        print("正在测试...\n")
        success, latency, info = test_rpc(custom_rpc)
        if success:
            print(f"✅ 自定义RPC可用! 延迟: {latency:.0f}ms | {info}\n")
        else:
            print(f"❌ 自定义RPC不可用: {info}\n")
        print("-" * 80 + "\n")
    
    print("测试公共RPC节点...\n")
    print(f"{'节点':<50} {'状态':<8} {'延迟':<12} {'信息'}")
    print("-" * 80)
    
    results = []
    
    for rpc in BSC_RPCS:
        success, latency, info = test_rpc(rpc)
        
        # 格式化输出
        rpc_display = rpc[:47] + "..." if len(rpc) > 50 else rpc
        status = "✅" if success else "❌"
        latency_str = f"{latency:.0f}ms" if success else "N/A"
        
        print(f"{rpc_display:<50} {status:<8} {latency_str:<12} {info}")
        
        if success:
            results.append((rpc, latency))
    
    print("-" * 80 + "\n")
    
    # 显示推荐
    if results:
        results.sort(key=lambda x: x[1])  # 按延迟排序
        best_rpc, best_latency = results[0]
        
        print(f"🎯 推荐使用: {best_rpc}")
        print(f"   延迟: {best_latency:.0f}ms (最快)\n")
        
        print("可用节点统计:")
        print(f"  总计: {len(BSC_RPCS)} 个")
        print(f"  可用: {len(results)} 个")
        print(f"  不可用: {len(BSC_RPCS) - len(results)} 个\n")
        
        if len(results) >= 3:
            print("✅ 多个节点可用，程序可以正常运行！")
        elif len(results) >= 1:
            print("⚠️  仅有少数节点可用，建议配置自定义RPC")
        else:
            print("❌ 没有可用节点，请检查网络连接或配置自定义RPC")
    else:
        print("❌ 所有公共RPC节点都不可用！")
        print("\n建议:")
        print("  1. 检查网络连接")
        print("  2. 尝试使用VPN")
        print("  3. 在.env文件中配置自定义RPC节点")
        print("\n自定义RPC配置示例:")
        print("  BSC_RPC_URL=https://your-rpc-url.com")
    
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    main()

