# 안드로이드 앱 빌드 — 이 파일을 오른쪽 클릭 > PowerShell 로 실행
#
#   .\build.ps1            APK 만들기 (app/build/outputs/apk/debug/app-debug.apk)
#   .\build.ps1 install    만들고 연결된 폰에 넣기 (디버그 키)
#   .\build.ps1 test       폰 없이 화면 그림만 PNG 로 뽑기 (app/build/미리보기/)
#   .\build.ps1 release    나눠줄 APK (고정 키로 서명. keystore.properties 필요)
#   .\build.ps1 install-release  나눠줄 것과 **같은 서명**으로 내 폰에 넣기 ← 이걸 쓰는 게 낫다
#                          (디버그 키로 깔아 두면 나중에 릴리스판으로 못 덮어쓴다)
#
# ★ 한글 경로 문제 — **유닛 테스트에서만 터진다**
#   이 저장소는 '13. 클로드 사용량' 아래에 있는데, Gradle 이 테스트를 돌릴 때
#   한글이 든 클래스패스를 자식 JVM 에 제대로 못 넘겨 테스트가 통째로 실패한다.
#   **APK 빌드는 한글 경로에서도 된다.** 그래서 test 일 때만 ASCII 경로(정션)를 거친다 —
#   정션이 망가져도 APK 빌드는 안 막힌다. 같은 이유로 gradle.properties 에
#   android.overridePathCheck=true 가 필요하다.

param([string]$Task = "build")

$ErrorActionPreference = 'Stop'
$real = $PSScriptRoot
$link = Join-Path $env:LOCALAPPDATA 'cooldown-android'

# 정션이 망가져도 Test-Path 는 참이고 **읽기까지 멀쩡한** 경우가 있다. 그런데 쓰기만
# 조용히 사라져서 Gradle 이 "Failed to create directory" 로 죽는다. 그래서 읽히는지가
# 아니라 **정션으로 쓴 것이 저장소에 실제로 나타나는지**로 판정한다.
function Test-JunctionWrites {
    if (-not (Test-Path $link)) { return $false }
    $name = "_junction_check"
    try { New-Item -ItemType Directory -Force (Join-Path $link $name) -ErrorAction Stop | Out-Null }
    catch { return $false }
    $landed = Test-Path (Join-Path $real $name)
    Remove-Item (Join-Path $real $name) -Force -Recurse -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $link $name) -Force -Recurse -ErrorAction SilentlyContinue
    return $landed
}

function Get-AsciiPath {
    if (Test-JunctionWrites) { return $link }
    if (Test-Path $link) {
        # 정션이면 링크만 지운다(저장소 내용은 안 건드림). 진짜 폴더면 통째로 지운다.
        $item = Get-Item $link -Force
        if ($item.LinkType -eq 'Junction') { [IO.Directory]::Delete($link, $false) }
        else { Remove-Item $link -Recurse -Force }
        Write-Host "망가진 빌드 경로를 지웠다: $link"
    }
    New-Item -ItemType Junction -Path $link -Target $real | Out-Null
    Write-Host "빌드용 ASCII 경로 만듦: $link"
    if (-not (Test-JunctionWrites)) { throw "빌드용 ASCII 경로를 못 만들었다: $link" }
    return $link
}

$env:JAVA_HOME = Join-Path $env:LOCALAPPDATA 'Android\jdk'
$env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
if (-not (Test-Path $env:JAVA_HOME)) { throw "JDK 가 없다: $env:JAVA_HOME" }

# 테스트만 ASCII 경로가 필요하다. 나머지는 저장소에서 바로.
if ($Task -eq 'test') { Set-Location (Get-AsciiPath) } else { Set-Location $real }

switch ($Task) {
    "install" { & .\gradlew.bat installDebug --console=plain }
    "install-release" { & .\gradlew.bat installRelease --console=plain }
    "test"    { & .\gradlew.bat testDebugUnitTest --console=plain }
    "release" { & .\gradlew.bat assembleRelease lintRelease --console=plain }
    default   { & .\gradlew.bat assembleDebug lintDebug --console=plain }
}
if ($LASTEXITCODE -ne 0) { throw "빌드 실패 ($LASTEXITCODE)" }

$kind = if ($Task -eq 'release') { 'release\app-release.apk' } else { 'debug\app-debug.apk' }
$apk = Join-Path $real "app\build\outputs\apk\$kind"
if (Test-Path $apk) {
    $mb = [math]::Round((Get-Item $apk).Length / 1MB, 1)
    Write-Host ""
    Write-Host "완성: $apk  ($mb MB)"
}
