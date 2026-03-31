$content = @"
[WHOLE FILE CONTENT HERE]
"@
$content | Set-Content -Path services/race_service.py -Encoding utf8
