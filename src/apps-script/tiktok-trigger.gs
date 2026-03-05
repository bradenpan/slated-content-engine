/**
 * Google Sheets onEdit trigger for the Slated TikTok Pipeline.
 *
 * Watches specific cells in the TikTok Content Queue tab and dispatches
 * GitHub Actions workflows via repository_dispatch events.
 *
 * Setup:
 * 1. Open the TikTok Google Sheet → Extensions → Apps Script
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
 * - Content Queue tab, all column M reviewed → tiktok-promote-and-schedule
 *   (Column M = Status, column index 13)
 */

function onSheetEdit(e) {
  var sheet = e.source.getActiveSheet();
  var range = e.range;
  var newValue = e.value;

  // Content Queue tab, column M (col 13): content approval
  // Fires when ALL data rows have a terminal status (approved / rejected)
  if (sheet.getName() === "Content Queue" && range.getColumn() === 13) {
    if (allContentReviewed(sheet)) {
      triggerGitHubWorkflow("tiktok-promote-and-schedule");
    }
  }
}

function triggerGitHubWorkflow(eventType) {
  var token = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");
  var repo = "bradenpan/slated-content-engine";

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

  var ids = sheet.getRange(2, 1, lastRow - 1, 1).getValues();        // Column A: IDs
  var statuses = sheet.getRange(2, 13, lastRow - 1, 1).getValues();   // Column M: Status
  var terminal = ["approved", "rejected"];

  for (var i = 0; i < ids.length; i++) {
    var id = ids[i][0].toString().trim();
    if (!id) continue;

    var status = statuses[i][0].toString().trim();
    if (terminal.indexOf(status) === -1) return false;
  }

  return true;
}
