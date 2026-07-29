# 안드로이드 앱 빌드 — 이 파일을 오른쪽 클릭 > PowerShell 로 실행
#
#   .\build.ps1            APK 만들기 (app/build/outputs/apk/debug/app-debug.apk)
#   .\build.ps1 install    만들고 USB 로 연결된 폰에 넣기
#   .\build.ps1 test       폰 없이 화면 그림만 PNG 로 뽑기 (app/build/미리보기/)
#
# ★ 한글 경로 문제
#   이 저장소는 '13. 클로드 사용량' 아래에 있는데, Gradle 이 테스트를 돌릴 때
#   한글이 든 클래스패스를 자식 JVM 에 제대로 못 넘겨 테스트가 통째로 실패한다.
#   그래서 ASCII 경로에 정션(바로가기 비슷한 것)을 만들어 **거기서** 빌드한다.
#   결과물은 정션 너머 진짜 폴더에 그대로 쌓이므로 신경 쓸 게 없다.

param([string]$Task = "build")

$ErrorActionPreference = 'Stop'
$real = $PSScriptRoot
$link = Join-Path $env:LOCALAPPDATA 'cooldown-android'

# 정션이 끊겨 있어도 Test-Path 는 참이다 — 실제로 저장소가 보이는지로 판정한다.
# (끊긴 정션에 쓰면 '됐다' 고 하고선 아무 데도 안 남아, Gradle 이 폴더를 못 만든다며 죽는다)
if (Test-Path $link) {
    if (-not (Test-Path (Join-Path $link 'settings.gradle.kts'))) {
        cmd /c rmdir "$link"
        Write-Host "끊긴 빌드 경로를 지웠다: $link"
    }
}
if (-not (Test-Path $link)) {
    New-Item -ItemType Junction -Path $link -Target $real | Out-Null
    Write-Host "빌드용 ASCII 경로 만듦: $link"
}

$env:JAVA_HOME = Join-Path $env:LOCALAPPDATA 'Android\jdk'
$env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
if (-not (Test-Path $env:JAVA_HOME)) { throw "JDK 가 없다: $env:JAVA_HOME" }

Set-Location $link
switch ($Task) {
    "install" { & .\gradlew.bat installDebug --console=plain }
    "test"    { & .\gradlew.bat testDebugUnitTest --console=plain }
    "release" { & .\gradlew.bat assembleRelease --console=plain }
    default   { & .\gradlew.bat assembleDebug lintDebug --console=plain }
}
if ($LASTEXITCODE -ne 0) { throw "빌드 실패 ($LASTEXITCODE)" }

$apk = Join-Path $real 'app\build\outputs\apk\debug\app-debug.apk'
if (Test-Path $apk) {
    $mb = [math]::Round((Get-Item $apk).Length / 1MB, 1)
    Write-Host ""
    Write-Host "완성: $apk  ($mb MB)"
}
