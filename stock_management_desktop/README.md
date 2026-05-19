# Stock Management Desktop App

A fresh desktop stock management app built with Python, Tkinter, and SQLite.

## What It Includes

- A more polished desktop interface with dashboard cards and separate tabs
- Startup splash screen for a more app-like launch experience
- Login system with admin and cashier roles
- Product management for add, edit, delete, and search
- Barcode field support with barcode lookup and scan-to-sell flow
- Phone-to-app barcode scanning over the same local Wi-Fi network
- Stock in and stock out adjustments
- Sales recording that automatically reduces stock
- Sales history tracking
- Daily sales totals and today's sales summary
- Searchable sales history
- Receipt file creation and Windows print support for sales
- CSV export for inventory and sales reports
- Database backup and restore from inside the app
- Custom application icon for both the window and packaged EXE
- Local SQLite storage using `inventory.db`

## Run The App

Open a terminal in this folder and run:

`python main.py`

The database file is created automatically when the app starts.

When running the packaged Windows app, the database and receipts are stored in a persistent user data folder:

`%LOCALAPPDATA%\Idana Technologies and Projects PTY LTD\StockManagementApp`

## Login

The app now starts with a login screen.

Default accounts:

- `admin` / `admin123`
- `cashier` / `cashier123`

Account features:

- change password from inside the app
- log out without closing the app manually

Roles:

- `admin` can add, edit, delete, and restore database backups
- `cashier` can search, scan, adjust stock, record sales, print receipts, export reports, and create backups

## Backup And Restore

Open the `Sales & Reports` tab to:

- create a backup copy of the database
- restore the app from a previous backup file
- open the most recent receipt created in the current app session
- print the most recent receipt created in the current app session

Restoring a backup replaces the current inventory and sales data, so use it carefully.

## Receipts

When recording a sale, you can choose to:

- create a receipt file
- print the receipt after saving the sale

Receipt files are saved in the `receipts` folder inside the project directory.

## Daily Sales

Open the `Sales & Reports` tab to see:

- recent sales history
- search recent sales by date, product, customer, or notes
- daily sales totals grouped by date
- today's sales count
- today's revenue

## Barcode Support

You can now:

- save a barcode on each product
- search for a product by barcode
- scan a barcode and open the sale flow quickly
- scan a barcode from a phone and send it into the desktop app

On the `Inventory` tab, use the barcode field with:

- `Find Barcode`
- `Scan Sale`
- `Phone Scanner`

Phone scanning notes:

- your phone and desktop must be on the same Wi-Fi network
- click `Phone Scanner` in the app to get the local address
- open that address on your phone browser
- scan and send the barcode back to the app

## Build An EXE

1. Install the build dependency:

   `pip install -r requirements.txt`

2. Run the build script:

   `build_exe.bat`

3. Find the generated app in:

   `dist\StockManagementApp.exe`

## Build A Windows Installer

1. Build the EXE first:

   `build_exe.bat`

2. Install Inno Setup on your computer if it is not already installed.

3. Run the installer build script:

   `build_installer.bat`

4. Find the generated installer in:

   `installer_output\StockManagementAppInstaller.exe`

## Files

- `main.py` - desktop application
- `inventory.db` - local database created at runtime
- `assets\app_icon.ico` and `assets\app_icon.png` - app icon files
- `requirements.txt` - build dependency list
- `build_exe.bat` - helper script for packaging into an EXE
- `installer.iss` - Inno Setup installer definition
- `build_installer.bat` - helper script for building a Windows installer
- `version_info.txt` - EXE version metadata used by PyInstaller
