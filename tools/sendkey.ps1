param(
    [Parameter(Mandatory=$true)][string[]]$Keys,   # e.g. RETURN,SPACE,W,A,S,D,LSHIFT
    [int]$HoldMs = 80,
    [int]$GapMs = 400,
    [string]$ProcName = "Vpw64Recompiled"
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class KeySend {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint uCode, uint uMapType);
    public const uint KEYEVENTF_KEYUP = 0x0002;
    public const uint KEYEVENTF_SCANCODE = 0x0008;
    public const uint KEYEVENTF_EXTENDEDKEY = 0x0001;
    public static void Press(byte vk, int holdMs, bool extended) {
        byte scan = (byte)MapVirtualKey(vk, 0);
        uint flags = KEYEVENTF_SCANCODE | (extended ? KEYEVENTF_EXTENDEDKEY : 0);
        keybd_event(vk, scan, flags, UIntPtr.Zero);
        System.Threading.Thread.Sleep(holdMs);
        keybd_event(vk, scan, flags | KEYEVENTF_KEYUP, UIntPtr.Zero);
    }
}
"@
$vkMap = @{
    "RETURN" = 0x0D; "SPACE" = 0x20; "LSHIFT" = 0xA0; "ESCAPE" = 0x1B
    "W" = 0x57; "A" = 0x41; "S" = 0x53; "D" = 0x44
    "I" = 0x49; "J" = 0x4A; "K" = 0x4B; "L" = 0x4C
    "Q" = 0x51; "E" = 0x45; "R" = 0x52; "F" = 0x46
    "UP" = 0x26; "DOWN" = 0x28; "LEFT" = 0x25; "RIGHT" = 0x27
}
$p = Get-Process $ProcName -ErrorAction Stop
[KeySend]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 300
$extendedKeys = @("UP", "DOWN", "LEFT", "RIGHT")
foreach ($k in $Keys) {
    $vk = $vkMap[$k.ToUpper()]
    if ($null -eq $vk) { throw "unknown key $k" }
    [KeySend]::Press([byte]$vk, $HoldMs, ($extendedKeys -contains $k.ToUpper()))
    Start-Sleep -Milliseconds $GapMs
}
"sent: $($Keys -join ' ')"
