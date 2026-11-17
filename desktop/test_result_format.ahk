#Requires AutoHotkey v2.0
#Include result_format.ahk
for payload in ["OK`r`n完整优化结果`r`n第二行", "OK`n完整优化结果`n第二行"] {
    result := ParseWorkerOutput(payload)
    if !result.ok || result.text != "完整优化结果`n第二行"
        ExitApp(1)
}
for payload in ["ERROR`r`n请求失败", "ERROR`n请求失败"] {
    result := ParseWorkerOutput(payload)
    if result.ok || result.text != "请求失败"
        ExitApp(2)
}
if ParseWorkerOutput("OK`r`n").ok || ParseWorkerOutput("乱码").ok
    ExitApp(3)
FileAppend("PASS: LF/CRLF success, errors and invalid results`n", "*")
ExitApp(0)
