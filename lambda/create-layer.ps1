# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install packages
pip install numpy==2.1.3 librosa==0.11.0 scipy==1.15.2

# ----- LAYER 1: NumPy and Librosa -----
# Create directory structure for the first layer
mkdir -p layer1\python

# Create minimal NumPy package
$minimalNumpy = @(
    "numpy\__init__.py",
    "numpy\*.pyd",
    "numpy\core",
    "numpy\lib\__init__.py",
    "numpy\lib\function_base.py",
    "numpy\lib\arraypad.py",
    "numpy\lib\type_check.py",
    "numpy\lib\utils.py",
    "numpy\lib\_version.py"
)

foreach ($path in $minimalNumpy) {
    $sourcePath = ".\venv\Lib\site-packages\" + $path
    $targetDir = Split-Path -Path ("layer1\python\" + $path) -Parent
    
    if (!(Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    
    if ($path.Contains("*")) {
        Copy-Item -Path $sourcePath -Destination $targetDir -Recurse -Force
    } else {
        $targetPath = "layer1\python\" + $path
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
    }
}

# Create minimal Librosa package (just for load and stft)
$minimalLibrosa = @(
    "librosa\__init__.py",
    "librosa\core\__init__.py",
    "librosa\core\audio.py",
    "librosa\core\spectrum.py",
    "librosa\core\convert.py"
)

foreach ($path in $minimalLibrosa) {
    $sourcePath = ".\venv\Lib\site-packages\" + $path
    $targetDir = Split-Path -Path ("layer1\python\" + $path) -Parent
    
    if (!(Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    
    Copy-Item -Path $sourcePath -Destination ("layer1\python\" + $path) -Force
}

# Copy essential dependencies for librosa
$librosaEssentialDeps = @(
    "soundfile",
    "audioread",
    "pooch",
    "llvmlite",
    "numba"
)

foreach ($dep in $librosaEssentialDeps) {
    if (Test-Path ".\venv\Lib\site-packages\$dep") {
        Copy-Item -Path ".\venv\Lib\site-packages\$dep" -Destination "layer1\python\" -Recurse -Force
    }
}

# ----- LAYER 2: SciPy (just ndimage.maximum_filter) -----
mkdir -p layer2\python\scipy

# Create minimal SciPy package with just ndimage.maximum_filter
$minimalScipy = @(
    "scipy\__init__.py",
    "scipy\_distributor_init.py",
    "scipy\*.pyd",
    "scipy\ndimage\__init__.py",
    "scipy\ndimage\filters.py",
    "scipy\ndimage\_filters.py",
    "scipy\ndimage\_ni_docstrings.py",
    "scipy\ndimage\_ni_support.py",
    "scipy\ndimage\*.pyd"
)

foreach ($path in $minimalScipy) {
    $sourcePath = ".\venv\Lib\site-packages\" + $path
    $targetDir = Split-Path -Path ("layer2\python\" + $path) -Parent
    
    if (!(Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    
    if ($path.Contains("*")) {
        Copy-Item -Path $sourcePath -Destination $targetDir -Recurse -Force
    } else {
        $targetPath = "layer2\python\" + $path
        Copy-Item -Path $sourcePath -Destination $targetPath -Force
    }
}

# Create the ZIP files
Compress-Archive -Path layer1\* -DestinationPath numpy-librosa-layer.zip -Force
Compress-Archive -Path layer2\* -DestinationPath scipy-layer.zip -Force

# Get the sizes
$layer1Size = (Get-ChildItem -Recurse layer1 | Measure-Object -Property Length -Sum).Sum / 1MB
$layer2Size = (Get-ChildItem -Recurse layer2 | Measure-Object -Property Length -Sum).Sum / 1MB

Write-Output "Layer 1 (NumPy + Librosa) size: $layer1Size MB"
Write-Output "Layer 2 (SciPy) size: $layer2Size MB"
Write-Output "Lambda layers created: numpy-librosa-layer.zip and scipy-layer.zip"