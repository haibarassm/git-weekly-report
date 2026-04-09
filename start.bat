@echo off
REM NAPS Git Weekly Report Generator 启动脚本 (Windows)

echo ===================================
echo   NAPS Git Weekly Report Generator
echo ===================================
echo.

REM 获取当前分支
for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set CURRENT_BRANCH=%%i
if "%CURRENT_BRANCH%"=="" set CURRENT_BRANCH=unknown
echo 当前分支: %CURRENT_BRANCH%

REM 设置镜像标签
set IMAGE_TAG=naps-report-generator:latest

echo 镜像标签: %IMAGE_TAG%
echo.

REM 检查配置文件
if not exist "config.json" (
    echo config.json not found
    exit /b 1
)
echo config.json OK
echo.

REM 构建Docker镜像
echo Building Docker image...
docker build -t %IMAGE_TAG% .

if errorlevel 1 (
    echo Docker build failed
    exit /b 1
)
echo Build OK
echo.

REM 停止并删除旧容器
set CONTAINER_NAME=report-generator
echo Removing old container...
docker stop %CONTAINER_NAME% 2>nul
docker rm %CONTAINER_NAME% 2>nul

REM 启动Docker容器
echo Starting container...
set PROJECT_PATH=%cd%
for %%i in ("%PROJECT_PATH%") do set BASE_DIR=%%~dpi

docker run -d ^
    --name %CONTAINER_NAME% ^
    --add-host=host.docker.internal:host-gateway ^
    -p 7861:7860 ^
    -v "%PROJECT_PATH%\config.json:/app/config.json" ^
    -v "%PROJECT_PATH%\output:/app/output" ^
    -v "%BASE_DIR%:/app/project:ro" ^
    -e PROJECT_BASE_DIR=/app/project ^
    -e LANGCHAIN_API_KEY=%LANGCHAIN_API_KEY% ^
    --restart unless-stopped ^
    %IMAGE_TAG%

if errorlevel 1 (
    echo Docker run failed
    exit /b 1
)

echo.
echo ===================================
echo   Started!
echo ===================================
echo.
echo URL:       http://localhost:7861
echo Branch:    %CURRENT_BRANCH%
echo Image:     %IMAGE_TAG%
echo Projects:  %BASE_DIR%
echo.
echo Logs:      docker logs -f %CONTAINER_NAME%
echo Stop:      docker stop %CONTAINER_NAME%
echo Remove:    docker rm -f %CONTAINER_NAME%
echo.
