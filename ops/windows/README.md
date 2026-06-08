# Windows 调度配置

## 安装

```powershell
cd D:\Newclaude\nev-brief
.\ops\windows\install-scheduled-task.ps1
```

会创建名为 "NEV-Daily-Brief" 的 Scheduled Task，每天 06:00 跑 `run-daily.ps1`。

## 验证

```powershell
Get-ScheduledTask -TaskName "NEV-Daily-Brief" | Select-Object TaskName, State, Triggers
```

## 手动 trigger（测试）

```powershell
Start-ScheduledTask -TaskName "NEV-Daily-Brief"
Get-Content -Tail 50 -Wait .\logs\daily-$(Get-Date -Format yyyyMMdd).log
```

## 卸载

```powershell
Unregister-ScheduledTask -TaskName "NEV-Daily-Brief" -Confirm:$false
```

## 日志位置

`D:\Newclaude\nev-brief\logs\daily-YYYYMMDD.log`

## Mac mini 迁移

后续 Mac mini 部署见 `ops/launchd/README.md` 与 spec §7.5。
