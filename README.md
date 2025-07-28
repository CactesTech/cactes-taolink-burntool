# Python BurnTool for TaoLink TK8620

## How To Program TK8620

![image-20250728121750951](https://img.cactes.com/20250728-121803-645.png)

Connections like above, RTS is used to trigger TK8620 auto reboot.

Skip conda environment setup if you don't use conda, you can install burntool directly with pip.

```bash
conda create -n burntool python=3.12
conda activate burntool
pip install -U burntool
```

To load firmware to TK8620, use the following command:

```bash
burntoolcli host --port=COM5 --fw firmware.hex run
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
