# Python BurnTool for TaoLink TK8620

## Development Environment Setup

```bash
git clone https://github.com/CactesTech/cactes-taolink-burntool.git
pip install -r requirements.txt
```

## How To?

### Program TK8620 (conda)

```bash
conda create -n burntool python=3.12
conda activate burntool
pip install -U burntool
```

```bash
burntoolcli host --port=COM5 --fw firmware.hex run
```

### TK8620 OTA Protocol Parser (aka. the sniffer)

Parser mode is used to capture the OTA protocol from the TK8620 device. This helps understand the OTA procedure quickly.

```bash
burntoolcli parser --port=COM39 run
```

### Simulate a TK8620 OTA Device

```bash
burntoolcli device --port=COM39 run
```

## About Taolink Private Hex File

Taolink projects provide a non-standard hex file, if you need a standard hex file, use the following Nuclei Studio configuration.

```
${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}.hex" && "${PWD}\..\..\..\..\..\..\..\Release\Scripts\intelhex2strhex.exe" ${ProjName}.hex


to

${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}.hex" && ${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}_real.hex" && "${PWD}\..\..\..\..\..\..\..\Release\Scripts\intelhex2strhex.exe" ${ProjName}.hex
```

![image-20240319160430168](https://img.cactes.com/20240319-160431-453.png)


## Work In Progress

- A GUI interface (Maybe)
