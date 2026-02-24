/**
 * Google Sheets onEdit trigger for the Slated Pinterest Pipeline.
 *
 * Watches specific cells in the Weekly Review and Content Queue tabs
 * and dispatches GitHub Actions workflows via repository_dispatch events.
 *
 * Setup:
 * 1. Open the Google Sheet → Extensions → Apps Script
 * 2. Paste this entire file into Code.gs
 * 3. Go to Project Settings → Script Properties
 *    → Add property: GITHUB_TOKEN = <your GitHub PAT with repo scope>
 * 4. Set up an installable trigger:
 *    → Triggers (clock icon) → Add Trigger
 *    → Function: onSheetEdit
 *    → Event type: On edit
 *    → (The simple onEdit trigger does NOT work for UrlFetchApp;
 *       you MUST use an installable trigger.)
 *
 * Trigger map:
 * - Weekly Review tab, cell B3 = "approved"  → generate-content
 * - Content Queue tab, all column J reviewed → deploy-to-preview
 * - Content Queue tab, cell N1 = "run"       → regen-content
 * - Weekly Review tab, cell B4 = "approved"  → promote-and-schedule
 */

function onSheetEdit(e) {
  var sheet = e.source.getActiveSheet();
  var range = e.range;
  var newValue = e.value;

  // Weekly Review tab, cell B3: plan approval → triggers content generation
  if (sheet.getName() === "Weekly Review" && range.getRow() === 3 && range.getColumn() === 2) {
    if (newValue === "approved") {
      triggerGitHubWorkflow("generate-content");
    }
  }

  // Content Queue tab, column J (col 10): content approval → triggers preview deploy
  // Only fires when ALL data rows are "approved" or "rejected" (no pending_review, no regen*)
  if (sheet.getName() === "Content Queue" && range.getColumn() === 10) {
    if (allContentReviewed(sheet)) {
      triggerGitHubWorkflow("deploy-to-preview");
    }
  }

  // Content Queue tab, cell N1 (row 1, col 14): regen trigger
  if (sheet.getName() === "Content Queue" && range.getRow() === 1 && range.getColumn() === 14) {
    if (newValue === "run") {
      triggerGitHubWorkflow("regen-content");
    }
  }

  // Weekly Review tab, cell B4: production approval → triggers promote + schedule
  if (sheet.getName() === "Weekly Review" && range.getRow() === 4 && range.getColumn() === 2) {
    if (newValue === "approved") {
      triggerGitHubWorkflow("promote-and-schedule");
    }
  }
}

function triggerGitHubWorkflow(eventType) {
  var token = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");
  var repo = "bradenpan/slated-pinterest-bot";

  UrlFetchApp.fetch("https://api.github.com/repos/" + repo + "/dispatches", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + token,
      "Accept": "application/vnd.github.v3+json"
    },
    payload: JSON.stringify({
      event_type: eventType
    })
  });
}

function allContentReviewed(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return false;

  var ids = sheet.getRange(2, 1, lastRow - 1, 1).getValues();       // Column A: IDs
  var statuses = sheet.getRange(2, 10, lastRow - 1, 1).getValues();  // Column J: Status
  var terminal = ["approved", "rejected"];

  for (var i = 0; i < ids.length; i++) {
    var id = ids[i][0].toString().trim();
    // Skip empty rows and the summary row
    if (!id || id === "QUALITY GATE STATS") continue;

    var status = statuses[i][0].toString().trim();
    if (terminal.indexOf(status) === -1) return false;  // pending_review, regen*, etc.
  }

  return true;
}

/** Convenience function for the "Run Regen" button drawing. */
function runRegen() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Content Queue");
  if (sheet) {
    sheet.getRange("N1").setValue("run");
  }
  triggerGitHubWorkflow("regen-content");
}
