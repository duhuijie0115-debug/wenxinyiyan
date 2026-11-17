ParseWorkerOutput(payload) {
    ; Accept files written with either Windows CRLF or Unix LF newlines.
    payload := StrReplace(payload, "`r`n", "`n")
    separator := InStr(payload, "`n")
    if !separator
        return {ok: false, text: "后台返回格式异常，请重试。"}
    status := SubStr(payload, 1, separator - 1)
    body := SubStr(payload, separator + 1)
    if status = "OK" && Trim(body)
        return {ok: true, text: body}
    if status = "ERROR"
        return {ok: false, text: body}
    return {ok: false, text: "后台返回格式异常，请重试。"}
}
