<#
.SYNOPSIS
    Figma 节点与设计资产自动化提取工具 (Skill C02-UI视觉设计 核心适配器)
.DESCRIPTION
    解析 Figma URL，提取目标 Frame/Component 的 Auto Layout 布局、色彩、文字样式及高保真 PNG 渲染图。
.PARAMETER Url
    Figma 文件或节点的完整 URL (包含 fileKey 与 node-id)
.PARAMETER OutDir
    提取资产保存目录
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$Url,

    [string]$OutDir = "$PSScriptRoot\..\..\..\..\antigravity\scratch\figma_assets"
)

$token = [Environment]::GetEnvironmentVariable("FIGMA_ACCESS_TOKEN", "User")
if (-not $token) {
    $token = [Environment]::GetEnvironmentVariable("FIGMA_ACCESS_TOKEN", "Process")
}
if (-not $token) {
    Write-Error "未找到 FIGMA_ACCESS_TOKEN，请先配置环境变量。"
    exit 1
}

# 1. 解析 Figma URL
# 格式例如: https://www.figma.com/design/:fileKey/:title?node-id=1-2
# 或: https://www.figma.com/file/:fileKey/...
$fileKey = ""
$nodeId = ""

if ($Url -match "(?:design|file)/([a-zA-Z0-9]+)") {
    $fileKey = $matches[1]
} else {
    Write-Error "无法从 URL 中识别 Figma fileKey: $Url"
    exit 1
}

if ($Url -match "node-id=([0-9\-\:]+)") {
    $nodeId = $matches[1] -replace "-", ":"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Figma 深度提取中..." -ForegroundColor Cyan
Write-Host "FileKey: $fileKey" -ForegroundColor Gray
Write-Host "NodeId:  $nodeId" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

$headers = @{
    "X-Figma-Token" = $token
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

try {
    # 2. 获取节点树与样式属性
    $nodeApiUrl = "https://api.figma.com/v1/files/$fileKey"
    if ($nodeId) {
        $nodeApiUrl += "/nodes?ids=$nodeId"
    }
    
    Write-Host "正在获取节点树数据..." -ForegroundColor Yellow
    $nodeData = Invoke-RestMethod -Uri $nodeApiUrl -Headers $headers -Method Get
    $jsonPath = Join-Path $OutDir "figma_node.json"
    $nodeData | ConvertTo-Json -Depth 15 | Out-File -FilePath $jsonPath -Encoding utf8
    Write-Host "节点数据已保存至: $jsonPath" -ForegroundColor Green

    # 3. 若有特定节点，提取高清渲染图
    if ($nodeId) {
        Write-Host "正在请求高清渲染切图 (scale=2)..." -ForegroundColor Yellow
        $imgApiUrl = "https://api.figma.com/v1/images/$fileKey?ids=$nodeId&format=png&scale=2"
        $imgData = Invoke-RestMethod -Uri $imgApiUrl -Headers $headers -Method Get
        
        $imgUrl = $imgData.images.$nodeId
        if ($imgUrl) {
            $imgPath = Join-Path $OutDir "figma_preview.png"
            Invoke-WebRequest -Uri $imgUrl -OutFile $imgPath -UseBasicParsing
            Write-Host "渲染图已下载至: $imgPath" -ForegroundColor Green
        }
    }

    Write-Host "`n✅ Figma 资产提取成功！" -ForegroundColor Green
} catch {
    Write-Error "Figma API 调用失败: $($_.Exception.Message)"
}
