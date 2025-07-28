# Python BurnTool for TaoLink TK8620 by Cactes Company

A Python programming tool specifically designed for TaoLink TK8620 chip, supporting firmware programming, OTA protocol parsing, and device simulation.

这是一个专为 TaoLink TK8620 芯片设计的 Python 烧录工具，支持固件烧录、OTA 协议解析和设备模拟功能。

## Feature | 功能特点

- Auto download, no need reboot manually | 自动下载，无需手动重启
- Support Taolink private hex file format | 支持 Taolink 私有 hex 文件格式
- Support firmware programming, OTA protocol parsing, and device simulation | 支持固件烧录、OTA 协议解析和设备模拟
- Easy to use command line interface | 易于使用的命令行接口

## How To Program TK8620 | 如何对 TK8620 进行编程烧录

![image-20250728121750951](https://img.cactes.com/20250728-121803-645.png)

Connections like above, RTS is used to trigger TK8620 auto reboot.

如上图所示的连接方式，RTS 引脚用于触发 TK8620 自动重启。

Skip conda environment setup if you don't use conda, you can install burntool directly with pip.

如果不使用 conda 环境，可以跳过环境设置，直接使用 pip 安装 burntool。

```bash
conda create -n burntool python=3.12
conda activate burntool
pip install -U burntool
```

To load firmware to TK8620, use the following command:

使用以下命令将固件加载到 TK8620：

```bash
burntoolcli host --port=COM5 --fw firmware.hex run
```

## About Taolink Private Hex File | 关于 Taolink 私有 Hex 文件格式

Taolink projects provide a non-standard hex file, if you need a standard hex file, use the following Nuclei Studio configuration.

Taolink 项目提供非标准的 hex 文件，如果需要标准的 hex 文件，请使用以下 Nuclei Studio 配置。

```bash
${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}.hex" && "${PWD}\..\..\..\..\..\..\..\Release\Scripts\intelhex2strhex.exe" ${ProjName}.hex


to

${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}.hex" && ${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}_real.hex" && "${PWD}\..\..\..\..\..\..\..\Release\Scripts\intelhex2strhex.exe" ${ProjName}.hex
```

![image-20240319160430168](https://img.cactes.com/20240319-160431-453.png)


## Work In Progress | 正在开发

- A GUI interface (Maybe) | 图形用户界面（可能）

- Auto scan all serial ports | 自动化搜索串口
