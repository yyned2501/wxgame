# 降低微信/微信小游戏进程的 CPU 抢占: 优先级 + 可选限核
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File set_low_cpu.ps1 -Priority BelowNormal [-AffinityCores 6]
param(
    [ValidateSet('Normal','AboveNormal','BelowNormal','Idle')][string]$Priority = 'BelowNormal',
    [int]$AffinityCores = 0
)
$procs = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -like 'WeChatAppEx*' -or $_.ProcessName -eq 'WeChat' -or $_.ProcessName -eq 'Weixin'
}
if (-not $procs) {
    Write-Output '未找到微信进程(可能还没启动)'
    exit 1
}
foreach ($p in $procs) {
    try {
        $p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]$Priority
        Write-Output ("{0} (PID {1}): 优先级 -> {2}" -f $p.ProcessName, $p.Id, $Priority)
    } catch {
        Write-Output ("{0} (PID {1}): 优先级设置失败 - {2}" -f $p.ProcessName, $p.Id, $_.Exception.Message)
    }
    if ($AffinityCores -gt 0) {
        $total = [Environment]::ProcessorCount
        $n = [Math]::Min($AffinityCores, $total)
        $mask = [int64]0
        for ($i = $total - $n; $i -lt $total; $i++) { $mask = $mask -bor ([int64]1 -shl $i) }
        try {
            $p.ProcessorAffinity = [IntPtr]$mask
            Write-Output ("{0} (PID {1}): CPU 亲和性 -> 末 {2} 核 (mask 0x{3:X})" -f $p.ProcessName, $p.Id, $n, $mask)
        } catch {
            Write-Output ("{0} (PID {1}): 亲和性设置失败 - {2}" -f $p.ProcessName, $p.Id, $_.Exception.Message)
        }
    }
}
exit 0
