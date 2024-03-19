# Python BurnTool for TaoLink TK8620

## Install python enviroment


```bash
pip install -r requirements.txt
```



## How To?

### Program TK8620

```bash
python burntoolcli.py host --port=COM6 --fw=real.hex run
```

REMARK: Taolink projects provide non-standard hex file, so you need to convert it to standard hex file by using the following Nuclei Studio configuration.

```
${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}.hex" && "${PWD}\..\..\..\..\..\..\..\Release\Scripts\intelhex2strhex.exe" ${ProjName}.hex


to

${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}.hex" && ${cross_prefix}${cross_objcopy}${cross_suffix} -O ihex "${ProjName}.elf" "${ProjName}_real.hex" && "${PWD}\..\..\..\..\..\..\..\Release\Scripts\intelhex2strhex.exe" ${ProjName}.hex
```

![image-20240319160430168](https://img.jiapeng.me/20240319-160431-453.png)

### TK8620 OTA Protocol Parser (aka. the sniffer)

Parser mode is used to capture the OTA protocol from the TK8620 device. This helps understand the OTA procedrue quickly.

```bash
```
python burntoolcli.py parser --port=COM39 run
```

### Simulate a TK8620 OTA Device

```
python burntoolcli.py device --port=COM39 run
```


## Work In Progress

- Auto changing the baud rate
- A GUI interface (Maybe)

