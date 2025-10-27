#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha Hunter 自动交易 - LI.FI版
使用LI.FI聚合器进行Alpha代币自动交易
"""

import os
import sys
from dotenv import load_dotenv
from alpha_hunter_lifi import AlphaHunter

load_dotenv()


def main():
    print("\n" + "=" * 60)
    print("          Alpha Hunter - LI.FI版")
    print("          聚合所有DEX，自动止盈")
    print("=" * 60)
    print()
    
    # 读取私钥
    private_key = os.getenv('BSC_PRIVATE_KEY')
    if not private_key:
        print("[错误] 未设置BSC_PRIVATE_KEY")
        print()
        print("请在 .env 文件中设置:")
        print("BSC_PRIVATE_KEY=你的私钥")
        print()
        input("按回车退出...")
        return
    
    try:
        # 初始化Alpha Hunter
        hunter = AlphaHunter(private_key)
        
        # 输入代币信息
        print("\n" + "=" * 60)
        print("输入代币信息")
        print("=" * 60)
        print()
        
        token_address = input("代币合约地址: ").strip()
        if not token_address:
            print("[错误] 代币地址不能为空")
            input("按回车退出...")
            return
        
        token_name = input("代币名称（可选，按Enter跳过）: ").strip()
        if not token_name:
            token_name = f"TOKEN_{token_address[:6]}"
        
        # 显示代币信息
        token_info = {
            'symbol': token_name,
            'address': token_address
        }
        
        print(f"\n正在通过LI.FI查询最优价格...")
        
        # 获取报价（预览）
        quote = hunter.trader.get_quote(
            from_token=hunter.trader.NATIVE_TOKEN,
            to_token=token_address,
            amount=hunter.initial_investment,
            slippage=hunter.slippage
        )
        
        wait_for_liquidity = False
        retry_interval = 30
        
        if not quote:
            print("\n" + "=" * 60)
            print("[警告] 未检测到流动性池")
            print("=" * 60)
            print()
            print("可能原因:")
            print("  1. 代币尚未添加流动性")
            print("  2. LI.FI暂时无法找到交易路径")
            print("  3. 代币地址错误")
            print()
            print("选项:")
            print("  1. 退出程序")
            print("  2. 循环等待流动性出现（推荐新币）")
            print("  3. 忽略并继续尝试买入")
            print()
            
            choice = input("请选择 (1/2/3): ").strip()
            
            if choice == '1':
                print("\n已取消")
                input("按回车退出...")
                return
            elif choice == '2':
                wait_for_liquidity = True
                print()
                interval_input = input("检测间隔（秒，默认30）: ").strip()
                if interval_input.isdigit():
                    retry_interval = int(interval_input)
                print()
                print(f"[模式] 循环等待模式")
                print(f"[间隔] 每 {retry_interval}秒 检测一次")
                print(f"[提示] 按 Ctrl+C 可随时停止")
                print()
            elif choice == '3':
                print("\n将尝试继续...")
            else:
                print("\n无效选择，已取消")
                input("按回车退出...")
                return
        
        # 确认信息
        print("\n" + "=" * 60)
        print("确认信息")
        print("=" * 60)
        print(f"代币: {token_name}")
        print(f"地址: {token_address}")
        print(f"投资: {hunter.initial_investment} BNB")
        print(f"滑点: {hunter.slippage*100}%")
        print(f"策略: 自动止盈 (2x/3x/5x/10x)")
        print(f"引擎: LI.FI聚合器")
        if wait_for_liquidity:
            print(f"模式: 🔄 循环等待流动性（每{retry_interval}秒检测）")
        print("=" * 60)
        print()
        
        if not wait_for_liquidity or quote:
            confirm = input("确认买入并自动监控? (y/n): ").lower()
            if confirm != 'y':
                print("已取消")
                input("按回车退出...")
                return
        
        # 执行买入
        print("\n" + "=" * 60)
        print("执行买入")
        print("=" * 60)
        print()
        
        if wait_for_liquidity:
            print("[开始] 循环检测流动性，一旦发现立即买入...")
            print("[提示] 按 Ctrl+C 可随时停止等待")
            print()
        
        success = hunter.hunt_alpha_token(
            token_info, 
            wait_for_liquidity=wait_for_liquidity,
            retry_interval=retry_interval
        )
        
        if success:
            print("\n[成功] 买入完成!")
        else:
            print("\n[失败] 买入失败，请查看日志")
            input("按回车退出...")
            return
        
        # 启动监控
        print("\n" + "=" * 60)
        print("启动自动监控")
        print("=" * 60)
        print()
        print("程序将持续运行，自动监控止盈...")
        print("按 Ctrl+C 停止")
        print()
        
        check_interval = int(os.getenv('CHECK_INTERVAL', '30'))
        hunter.run_monitor(check_interval)
        
    except KeyboardInterrupt:
        print("\n\n[中断] 用户取消操作")
    except Exception as e:
        print(f"\n[错误] 程序异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\n按回车退出...")


if __name__ == '__main__':
    main()

