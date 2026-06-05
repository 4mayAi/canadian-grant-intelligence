$project = gcloud config get-value project
Write-Host "Active GCP Project: $project" -ForegroundColor Green

# 1. Enable Cloud Scheduler API
Write-Host "Enabling cloudscheduler.googleapis.com API (this may take a moment)..." -ForegroundColor Cyan
gcloud services enable cloudscheduler.googleapis.com --quiet

# 2. Retrieve GitHub Token
Write-Host "Retrieving GitHub authentication token..." -ForegroundColor Cyan
$token = (gh auth token).Trim()

$location = "us-west1"
$repo = "4mayAi/canadian-grant-intelligence"
$workflow = "daily_mining_hubs_scraper.yml"
$uri = "https://api.github.com/repos/$repo/actions/workflows/$workflow/dispatches"
$headers = "Accept=application/vnd.github+json,Authorization=Bearer $token,X-GitHub-Api-Version=2022-11-28,User-Agent=GCP-Cloud-Scheduler,Content-Type=application/json"
$body = '{\"ref\":\"main\",\"inputs\":{\"lookback_days\":\"30\"}}'

$jobName = "daily-mining-hubs-scraper-trigger"
$schedule = "0 12 * * *" # 12:00 PM EDT (16:00 UTC)

Write-Host "Configuring Google Cloud Scheduler job: $jobName for $schedule Eastern..." -ForegroundColor Cyan

# Delete first to allow a clean overwrite
gcloud scheduler jobs delete $jobName --location=$location --quiet 2>$null

# Create the job with strict double quotes for PowerShell passing compatibility
gcloud scheduler jobs create http $jobName `
    --schedule="$schedule" `
    --time-zone="America/New_York" `
    --uri=$uri `
    --http-method="POST" `
    --headers=$headers `
    --message-body=$body `
    --location=$location `
    --quiet

Write-Host "Google Cloud Scheduler job '$jobName' successfully configured in project $project!" -ForegroundColor Green
