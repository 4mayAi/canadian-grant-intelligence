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
$workflow = "daily_grants_scraper.yml"
$uri = "https://api.github.com/repos/$repo/actions/workflows/$workflow/dispatches"
$headers = "Accept=application/vnd.github+json,Authorization=Bearer $token,X-GitHub-Api-Version=2022-11-28,User-Agent=GCP-Cloud-Scheduler,Content-Type=application/json"
$body = '{\"ref\":\"main\",\"inputs\":{\"run_type\":\"DEEP_DIVE\",\"lookback_days\":\"7\"}}'

# Define jobs
$jobs = @(
    @{ Name = "daily-grants-scraper-morning-trigger"; Schedule = "0 10 * * *" },
    @{ Name = "daily-grants-scraper-midday-trigger"; Schedule = "0 14 * * *" },
    @{ Name = "daily-grants-scraper-eod-trigger"; Schedule = "0 18 * * *" }
)

foreach ($job in $jobs) {
    Write-Host "Configuring Google Cloud Scheduler job: $($job.Name) for $($job.Schedule) Eastern..." -ForegroundColor Cyan
    
    # Delete first to allow a clean overwrite
    gcloud scheduler jobs delete $job.Name --location=$location --quiet 2>$null
    
    # Create the job with strict double quotes for PowerShell passing compatibility
    gcloud scheduler jobs create http $job.Name `
        --schedule="$($job.Schedule)" `
        --time-zone="America/New_York" `
        --uri=$uri `
        --http-method="POST" `
        --headers=$headers `
        --message-body=$body `
        --location=$location `
        --quiet
}

# Clean up test-job if exists
gcloud scheduler jobs delete test-job --location=$location --quiet 2>$null

Write-Host "All 3 Google Cloud Scheduler jobs successfully configured in project $project!" -ForegroundColor Green
