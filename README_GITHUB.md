# Alpha Hunter BSC 🚀

智能加密货币交易机器人，专为BNB Smart Chain设计。使用LI.FI聚合器获取最优价格，支持循环等待流动性和自动止盈。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![BSC](https://img.shields.io/badge/BSC-Mainnet-yellow)](https://www.bnbchain.org/)

## ✨ 核心特性

- 🎯 **循环等待流动性** - 新币开盘狙击利器，自动检测并买入
- 🔄 **LI.FI聚合器** - 聚合所有主流DEX，自动获取最优价格
- 📈 **智能止盈** - 2x/3x/5x/10x自动分批卖出
- 🛡️ **多RPC节点** - 6个节点自动切换，提高稳定性
- 💪 **API限流保护** - 智能请求管理，避免被限流
- 📊 **实时监控** - 自动监控持仓，达到目标自动卖出

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/Alpha_Hunter_BSC.git
cd Alpha_Hunter_BSC
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境

```bash
# 复制配置示例
copy env_example.txt .env

# 编辑.env文件，填入以下信息：
# - PRIVATE_KEY: 你的钱包私钥
# - INITIAL_INVESTMENT: 每次投资金额（BNB）
# - SLIPPAGE: 滑点容忍度
```

### 4. 启动程序

**Windows用户（推荐）:**
```bash
# 双击运行
启动.bat
```

**所有平台:**
```bash
python auto_trade_lifi.py
```

## 📖 使用场景

### 🎯 场景1: 新币开盘狙击

专为新币开盘设计，自动等待流动性出现并立即买入：

```
1. 启动程序
2. 输入代币地址
3. 选择"循环等待流动性"模式
4. 设置检测间隔（推荐15-30秒）
5. 程序自动循环检测，发现流动性立即买入！
```

### 💰 场景2: 交易已有流动性代币

适用于已上线的代币，直接买入并自动监控止盈：

```
1. 启动程序
2. 输入代币地址
3. 查看价格预览
4. 确认买入
5. 程序自动监控止盈
```

## 🎯 止盈策略

| 倍数 | 卖出比例 | 说明 |
|------|---------|------|
| 2x | 50% | 卖出一半回本，剩余是纯利润 |
| 3x | 10% | 锁定部分收益 |
| 5x | 20% | 大幅盈利，落袋为安 |
| 10x | 20% | 顶级收益，继续持有剩余 |

## 📊 检测间隔建议

| 场景 | 检测间隔 | 说明 |
|------|---------|------|
| 🔥 热门新币 | 15秒 | 快速响应，竞争激烈 |
| ⭐ 普通新币 | 30秒 | **推荐**，平衡性能 |
| 💤 低优先级 | 60秒 | 节省资源 |

## 🛠️ 功能菜单

使用 `启动.bat` 可访问所有功能：

```
1. 启动交易程序  - 开始交易和监控
2. 测试RPC连接   - 检测网络状态
3. 查看日志文件  - 查看运行记录
4. 查看持仓记录  - 查看当前持仓
5. 退出
```

## 📁 项目结构

```
Alpha_Hunter_BSC/
├── alpha_hunter_lifi.py          # 核心交易引擎
├── auto_trade_lifi.py            # 启动脚本
├── test_rpc_connection.py        # RPC测试工具
├── 启动.bat                      # Windows统一启动脚本
├── requirements.txt              # 依赖列表
├── env_example.txt               # 配置示例
├── README.md                     # 完整文档
├── 使用说明.txt                  # 简明指南
└── 问题排查指南.md               # 故障排查

文档/
├── 循环等待流动性功能说明.md
├── 新功能快速指南.txt
└── 版本说明.txt
```

## ⚠️ 重要提示

### 安全建议
- 🔒 **不要分享私钥**
- 🔒 **不要上传.env文件到GitHub**
- 🔒 **建议使用测试钱包进行初次测试**
- 🔒 **只投入你能承受损失的资金**

### 风险提示
- ⚠️ 加密货币交易有风险，可能导致资金损失
- ⚠️ 新币风险更高，可能归零
- ⚠️ 程序不保证盈利
- ⚠️ 请理解并接受可能的损失

## 🔧 常见问题

<details>
<summary><b>Q: 无法连接到BSC节点？</b></summary>

运行 `启动.bat` → 选择"测试RPC连接"检查网络，或在 `.env` 中配置自定义RPC节点。
</details>

<details>
<summary><b>Q: 循环等待会一直运行吗？</b></summary>

是的，直到检测到流动性或你按 `Ctrl+C` 中断。建议设置合理的检测间隔（30秒以上）。
</details>

<details>
<summary><b>Q: API限流怎么办？</b></summary>

程序内置限流保护。建议检测间隔设置为30秒以上，避免过度请求。
</details>

<details>
<summary><b>Q: 如何提高狙击成功率？</b></summary>

- 使用较短的检测间隔（15-30秒）
- 确保BNB余额充足
- 设置合理的滑点（10-20%）
- 使用快速的RPC节点
</details>

## 💻 系统要求

- **操作系统**: Windows 10/11, Linux, macOS
- **Python**: 3.8 或更高版本
- **内存**: 最低 512MB
- **网络**: 稳定的互联网连接
- **BNB余额**: 交易金额 + 0.005 BNB（Gas费预留）

## 📦 依赖包

```
web3>=6.0.0          # 以太坊/BSC交互
requests>=2.31.0     # HTTP请求
python-dotenv>=1.0.0 # 环境变量管理
eth-account>=0.8.0   # 账户管理
```

## 🌐 支持的网络

- ✅ BNB Smart Chain (BSC)

## 📈 版本历史

### v1.1.0 (2025-10-27) - 当前版本
- ✅ 新增循环等待流动性功能
- ✅ 修复BSC节点连接问题
- ✅ 优化API限流保护
- ✅ 改进错误提示和日志
- ✅ 新增RPC测试工具
- ✅ 统一启动脚本

### v1.0.0 (2025-10-20)
- 初始版本发布
- LI.FI聚合器集成
- 基础自动止盈功能

## 📚 文档

- [完整使用说明](README.md) - 详细文档
- [使用说明](使用说明.txt) - 快速指南
- [循环等待功能说明](循环等待流动性功能说明.md) - 新功能详解
- [问题排查指南](问题排查指南.md) - 故障排查

## 🔗 有用链接

- **BSCScan**: https://bscscan.com/
- **LI.FI**: https://li.fi/
- **PancakeSwap**: https://pancakeswap.finance/
- **BNB Chain**: https://www.bnbchain.org/

## 📞 获取帮助

- 📖 查看文档
- 💬 提交Issue
- 📧 联系支持

## 📜 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## ⚠️ 免责声明

- 本软件按"原样"提供，不提供任何明示或暗示的保证
- 加密货币交易具有高风险，可能导致资金损失
- 作者不对使用本软件造成的任何损失负责
- 请确保你了解相关风险并能够承受可能的损失
- 在使用真实资金前，请先进行充分测试

## 🙏 贡献

欢迎提交Pull Request或Issue！

## ⭐ Star支持

如果这个项目对你有帮助，请给个Star！⭐

---

**祝你交易顺利！🚀**

**版本**: v1.1.0 | **最后更新**: 2025-10-27 | **引擎**: LI.FI

