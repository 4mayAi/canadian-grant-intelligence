# Setup GCP Cloud Scheduler triggers for Canadian Grants Pipeline

$gcloudAuth = gcloud auth list --format="value(account)"
if (-not $gcloudAuth) {
    Write-Host "No active gcloud credentials found. Initiating gcloud auth login..." -ForegroundColor Yellow
    gcloud auth login
}

$project = gcloud config get-value project
if (-not $project) {
    $project = Read-Host "Please enter your GCP Project ID"
    gcloud config set project $project
}

Write-Host "Using GCP Project: $project" -ForegroundColor Green

$pat = Read-Host -Prompt "Please enter your GitHub Personal Access Token (PAT) with actions:write scope"
if (-not $pat) {
    Write-Error "GitHub PAT cannot be empty."
    exit
}

$location = "us-west1"
$repo = "4mayAi/canadian-grant-intelligence"
$workflow = "daily_grants_scraper.yml"
$uri = "https://api.github.com/repos/$repo/actions/workflows/$workflow/dispatches"
$headers = "Accept=application/vnd.github+json,Authorization=Bearer $pat,X-GitHub-Api-Version=2022-11-28,User-Agent=GCP-Cloud-Scheduler,Content-Type=application/json"
$body = '{\"ref\":\"main\",\"inputs\":{\"run_type\":\"DEEP_DIVE\",\"lookback_days\":\"7\"}}'

# Define jobs
$jobs = @(
    @{ Name = "daily-grants-scraper-morning-trigger"; Schedule = "0 10 * * *" },
    @{ Name = "daily-grants-scraper-midday-trigger"; Schedule = "0 14 * * *" },
    @{ Name = "daily-grants-scraper-eod-trigger"; Schedule = "0 18 * * *" }
)

foreach ($job in $jobs) {
    Write-Host "Configuring scheduler job: $($job.Name) for $($job.Schedule) Eastern..." -ForegroundColor Cyan
    # Try deleting first to allow a clean overwrite if it already exists
    gcloud scheduler jobs delete $job.Name --location=$location --quiet 2>$null
    
    gcloud scheduler jobs create http $job.Name `
        --schedule=$job.Schedule `
        --time-zone="America/New_York" `
        --uri=$uri `
        --http-method="POST" `
        --headers=$headers `
        --message-body=$body `
        --location=$location `
        --quiet
}

Write-Host "All 3 Cloud Scheduler jobs have been configured successfully in region: $location!" -ForegroundColor Green
