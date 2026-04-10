@echo off
REM NAPS 生成工具集 V0.7 启动脚本 (Windows)

echo ===================================
echo   NAPS 生成工具集 V0.7
echo ===================================
echo.

REM 获取当前分支
for /f "tokens=*" %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set CURRENT_BRANCH=%%i
if "%CURRENT_BRANCH%"=="" set CURRENT_BRANCH=unknown
echo 当前分支: %CURRENT_BRANCH%

REM 设置镜像标签
set IMAGE_TAG=naps-generator:latest
set CONTAINER_NAME=naps-generator

echo 镜像标签: %IMAGE_TAG%
echo.

REM 配置目录
if "%NAPS_CONFIG_DIR%"=="" set NAPS_CONFIG_DIR=%USERPROFILE%\.naps
if "%NAPS_PROJECTS_DIR%"=="" set NAPS_PROJECTS_DIR=%USERPROFILE%\projects

echo 配置目录: %NAPS_CONFIG_DIR%
echo 项目目录: %NAPS_PROJECTS_DIR%
echo.

REM 检查配置文件
if not exist "%NAPS_CONFIG_DIR%\naps.json" (
    echo 错误: 配置文件不存在 %NAPS_CONFIG_DIR%\naps.json
    echo 请先创建配置文件
    exit /b 1
)
echo naps.json OK
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
echo Removing old container...
docker stop %CONTAINER_NAME% 2>nul
docker rm %CONTAINER_NAME% 2>nul

REM 启动Docker容器
echo Starting container...

docker run -d ^
    --name %CONTAINER_NAME% ^
    --add-host=host.docker.internal:host-gateway ^
    -p 7861:7860 ^
    -v "%NAPS_CONFIG_DIR%\naps.json:/app/config/naps.json:ro" ^
    -v "%NAPS_CONFIG_DIR%\projects.json:/app/config/projects.json:ro" ^
    -v "%NAPS_PROJECTS_DIR%:/app/projects:ro" ^
    -v "%cd%\output:/app/output" ^
    -e NAPS_CONFIG_PATH=/app/config/naps.json ^
    -e NAPS_PROJECTS_PATH=/app/config/projects.json ^
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
echo.
echo 配置目录: %NAPS_CONFIG_DIR%
echo 项目目录: %NAPS_PROJECTS_DIR%
echo.
echo Logs:      docker logs -f %CONTAINER_NAME%
echo Stop:      docker stop %CONTAINER_NAME%
echo Remove:    docker rm -f %CONTAINER_NAME%
echo.
