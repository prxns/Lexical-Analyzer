param(
    [Parameter(Mandatory=$true)][string]$InputPdf,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Data.Pdf.PdfPageRenderOptions, Windows.Data.Pdf, ContentType=WindowsRuntime]
$methods = [System.WindowsRuntimeSystemExtensions].GetMethods()
$operationMethod = $methods | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and
    $_.GetGenericArguments().Length -eq 1 -and $_.GetParameters().Length -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
$actionMethod = $methods | Where-Object {
    $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and
    $_.GetParameters().Length -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
} | Select-Object -First 1
function Await-Operation($Operation, [Type]$ResultType) {
    $task = $operationMethod.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}
function Await-Action($Operation) {
    $task = $actionMethod.Invoke($null, @($Operation))
    $task.Wait()
}
$resolvedPdf = (Resolve-Path -LiteralPath $InputPdf).Path
$file = Await-Operation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($resolvedPdf)) ([Windows.Storage.StorageFile])
$document = Await-Operation ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
for ($index = 0; $index -lt $document.PageCount; $index++) {
    $page = $document.GetPage([uint32]$index)
    $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    $options = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $options.DestinationWidth = [uint32]1190
    $options.DestinationHeight = [uint32]1684
    Await-Action ($page.RenderToStreamAsync($stream, $options))
    $reader = New-Object Windows.Storage.Streams.DataReader ($stream.GetInputStreamAt(0))
    $null = Await-Operation ($reader.LoadAsync([uint32]$stream.Size)) ([uint32])
    $buffer = New-Object byte[] ([int]$stream.Size)
    $reader.ReadBytes($buffer)
    $destination = Join-Path $OutputDirectory ('page-{0:D2}.png' -f ($index + 1))
    [System.IO.File]::WriteAllBytes($destination, $buffer)
    $reader.Dispose()
    $stream.Dispose()
    $page.Dispose()
}
Write-Output ('Rendered {0} PDF pages' -f $document.PageCount)
