# To Release

```
rm -rf dist/ build/ *.egg-info/
python -m build
python -m twine upload dist/*
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

## 
