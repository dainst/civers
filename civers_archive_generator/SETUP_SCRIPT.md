# Application Setup Script

An automated setup script that handles the complete installation and configuration of the Archive Generator application.

## Quick Setup

```bash
# Clone the repository
git clone <repository-url>
cd civers_archive_generator

# Run the automated setup script
./application_setup.sh
```

That's it! The script will handle everything automatically.

## What the Script Does

The `application_setup.sh` script automates all the manual installation steps from the README:

### 1. **System Verification**

- Checks if you're in the correct project directory
- Verifies Docker and curl are installed
- Ensures Docker daemon is running

### 2. **Node.js v20 Installation**

- Installs Node Version Manager (nvm) if needed
- Installs and configures Node.js v20.x (required for Scoop)
- Sets Node.js v20 as the default version
- Verifies the installation

### 3. **Python Environment Setup**

- Installs uv package manager if needed
- Installs all Python dependencies via `uv sync`
- Installs Playwright browsers for Python

### 4. **Scoop Dependencies**

- Installs Scoop npm dependencies
- Installs Playwright Chromium browser for Scoop
- Verifies Scoop CLI functionality

### 5. **Permissions & Directories**

- Makes SingleFile binary executable
- Creates archives directory with proper permissions
- Sets up project folder permissions

### 6. **Kafka Infrastructure**

- Starts Docker Compose services (Kafka + Zookeeper)
- Waits for Kafka to be ready and responsive
- Verifies containers are running properly

### 7. **Installation Verification**

- Tests Node.js v20 is active
- Verifies Scoop CLI works
- Checks Python/Playwright integration
- Validates SingleFile binary permissions
- Confirms Docker containers are running

### 8. **Quick Application Test**

- Starts the application briefly
- Sends a test archive request
- Verifies basic functionality works

## Error Handling

The script includes comprehensive error checking:

- **Immediate Exit**: Stops on any error with clear error messages
- **Step Validation**: Each step is verified before proceeding
- **Detailed Logging**: Color-coded output with success/error/warning messages
- **Troubleshooting**: Provides specific guidance when errors occur

## Manual Fallback

If the automated script fails, you can follow the manual installation steps in [README.md](README.md#installation).

## After Setup

Once setup completes successfully:

1. **Start the application:**

   ```bash
   uv run python main.py
   ```

2. **Send test requests** (in another terminal):

   ```bash
   uv run python send_test_requests.py
   ```

3. **Check generated archives:**

   ```bash
   ls -la archives/
   ```

## Common Issues

**Permission Denied:**

```bash
chmod +x application_setup.sh
./application_setup.sh
```

**Docker Not Running:**

```bash
sudo systemctl start docker  # Linux
# or start Docker Desktop    # macOS/Windows
```

**Node.js Version Issues:**
The script automatically handles Node.js version management, but you may need to restart your terminal after setup.

**Network Issues:**
Ensure you have internet access for downloading dependencies.

## Script Features

- ✅ **Idempotent**: Safe to run multiple times
- ✅ **Validation**: Checks each step before proceeding
- ✅ **Detailed Output**: Clear progress and error messages
- ✅ **Cleanup**: Handles interruptions gracefully
- ✅ **Cross-platform**: Works on Linux and macOS
- ✅ **Prerequisites**: Checks system requirements first

## Customization

You can modify the script to:

- Skip certain steps by commenting them out in `main()`
- Change Node.js version by editing the `install_nodejs()` function
- Adjust timeout values for Kafka startup
- Add additional verification steps

The script is designed to be readable and maintainable for easy customization.
