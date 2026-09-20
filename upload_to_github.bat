@echo off
echo ==============================================
echo 🚀 UPLOADING PROJECT TO GITHUB...
echo ==============================================

echo [1/5] Initializing Git Repository...
git init

echo [2/5] Adding all safe files...
git add .

echo [3/5] Committing files...
git commit -m "Initial commit: The Wire Payments Compliance Leader"

echo [4/5] Setting up branch and remote...
git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/Akashtk07/The-Wire-Payments-Compliance-Leader.git

echo [5/5] Pushing to GitHub...
git push -u origin main

echo ==============================================
echo ✅ DONE! If there were no errors above, your code is uploaded!
echo ==============================================
pause
