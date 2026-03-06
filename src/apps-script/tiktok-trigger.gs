/**
 * Google Sheets onEdit trigger for the Slated TikTok Pipeline.
 *
 * Watches specific cells across the TikTok Google Sheet and dispatches
 * GitHub Actions workflows via repository_dispatch events.
 *
 * Setup:
 * 1. Open the TikTok Google Sheet -> Extensions -> Apps Script
 * 2. Paste this entire file into Code.gs
 * 3. Go to Project Settings -> Script Properties
 *    -> Add property: GITHUB_TOKEN = <your GitHub PAT with repo scope>
 * 4. Set up an installable trigger:
 *    -> Triggers (clock icon) -> Add Trigger
 *    -> Function: onSheetEdit
 *    -> Event type: On edit
 *    -> (The simple onEdit trigger does NOT work for UrlFetchApp;
 *       you MUST use an installable trigger.)
 *
 * Trigger map:
 * - Weekly Review B3 = "approved"       -> tiktok-generate-content
 * - Weekly Review B5 = "regen"          -> tiktok-regen-plan
 * - Weekly Review B3 = "pending_review" -> stale indicator on Content Queue
 * - Content Queue col O all reviewed    -> tiktok-promote-and-schedule (guarded)
 * - Content Queue R1 = "run"            -> tiktok-regen-content
 */

function onSheetEdit(e) {
  var sheet = e.source.getActiveSheet();
  var range = e.range;
  var tabName = sheet.getName();
  var col = range.getColumn();
  var row = range.getRow();
  // Use range.getValue() instead of e.value — e.value is undefined
  // for programmatic setValue() calls and multi-cell pastes.
  var newValue = range.getValue().toString().trim().toLowerCase();

  // === Weekly Review tab triggers ===
  if (tabName === "Weekly Review") {

    // B3: Plan status
    if (col === 2 && row === 3) {
      if (newValue === "approved") {
        // Guard: block approval while plan regen is in flight
        var b5 = sheet.getRange("B5").getValue().toString().trim().toLowerCase();
        if (b5 !== "idle" && b5 !== "") {
          sheet.getRange("B3").setValue("pending_review");
          sheet.getRange("B3").setNote("BLOCKED: B5 was '" + b5 + "' — wait for plan regen to complete, then re-approve.");
          return;
        }
        sheet.getRange("B6").setValue(new Date().toISOString());
        triggerGitHubWorkflow("tiktok-generate-content");
      }

      if (newValue === "pending_review") {
        // Write stale indicator to Content Queue S1
        var cqSheet = e.source.getSheetByName("Content Queue");
        if (cqSheet && cqSheet.getLastRow() > 1) {
          cqSheet.getRange("S1").setValue("⚠️ STALE — plan under revision");
        }
      }
    }

    // B5: Plan regen trigger
    if (col === 2 && row === 5 && newValue === "regen") {
      sheet.getRange("B6").setValue(new Date().toISOString());
      triggerGitHubWorkflow("tiktok-regen-plan");
    }
  }

  // === Content Queue tab triggers ===
  if (tabName === "Content Queue") {

    // Column O (col 15): content approval status
    // Fires when ALL data rows have a terminal status (approved / rejected)
    if (col === 15) {
      if (allContentReviewed(sheet)) {
        // Guard: only dispatch if Weekly Review B3 = "approved"
        // (prevents scheduling stale renders after backward phase transition)
        var wrSheet = e.source.getSheetByName("Weekly Review");
        if (wrSheet) {
          var b3 = wrSheet.getRange("B3").getValue().toString().trim().toLowerCase();
          if (b3 !== "approved") {
            sheet.getRange("S1").setValue("BLOCKED: Weekly Review B3 is '" + b3 + "' — plan not approved.");
            return;
          }
        }
        triggerGitHubWorkflow("tiktok-promote-and-schedule");
      }
    }

    // R1: Content regen trigger
    if (col === 18 && row === 1 && newValue === "run") {
      sheet.getRange("R2").setValue(new Date().toISOString());
      triggerGitHubWorkflow("tiktok-regen-content");
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
  var statuses = sheet.getRange(2, 15, lastRow - 1, 1).getValues();   // Column O: Status
  var terminal = ["approved", "rejected"];
  var foundValidRow = false;

  for (var i = 0; i < ids.length; i++) {
    var id = ids[i][0].toString().trim();
    if (!id) continue;

    foundValidRow = true;
    var status = statuses[i][0].toString().trim().toLowerCase();
    if (terminal.indexOf(status) === -1) return false;
  }

  return foundValidRow;
}

// === Convenience button functions ===

/**
 * Trigger plan-level regen manually (attach to a button drawing).
 * Sets B5 = "regen" which fires the onSheetEdit trigger.
 */
function runTikTokPlanRegen() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var wr = ss.getSheetByName("Weekly Review");
  if (wr) {
    wr.getRange("B5").setValue("regen");
  }
}

/**
 * Trigger content-level regen manually (attach to a button drawing).
 * Sets R1 = "run" which fires the onSheetEdit trigger.
 */
function runTikTokContentRegen() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cq = ss.getSheetByName("Content Queue");
  if (cq) {
    cq.getRange("R1").setValue("run");
  }
}
