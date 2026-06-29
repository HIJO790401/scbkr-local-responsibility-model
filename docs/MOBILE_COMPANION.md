# 手機連回本機電腦

## 手機端定位

手機端是操作入口，不是獨立模型主體，也不是完整獨立 Runtime。它不能獨立判定規則，不能繞過本機 Runtime，也不能繞過簽名、驗收與二次確認。

## activeBackendUrl 設定

手機端透過 activeBackendUrl 連回本機電腦。例如：

```text
http://192.168.1.23:8000
```

請依實際 backend port 調整。

## 同 Wi-Fi 要求

手機與電腦通常需要在同一 Wi-Fi / LAN。若使用 VPN、公司網路或訪客網路，裝置之間可能被隔離。

## 如何查 Windows 區網 IP

在 Windows PowerShell 執行：

```powershell
ipconfig
```

尋找 Wi-Fi 介面卡的 IPv4 Address，例如 192.168.x.x。

## Windows 防火牆注意事項

Windows 防火牆可能需要允許 SCBKR / FastAPI 通訊。只允許可信任私人網路，不建議把本機 backend 暴露到公網。
