function doGet(e) {
  const FILE_ID = "1kaw5PhHZQDzksb-i61UrWxoUE2uLe8Ex";

  try {
    const file = DriveApp.getFileById(FILE_ID);
    const fileName = file.getName().replace(/\.csv$/i, ""); // → "geolocation"

    // Use Drive's direct download URL instead of blob
    const downloadUrl = "https://drive.google.com/uc?export=download&id=" + FILE_ID;
    
    const response = UrlFetchApp.fetch(downloadUrl, {
      headers: {
        Authorization: "Bearer " + ScriptApp.getOAuthToken()
      },
      followRedirects: true,
      muteHttpExceptions: true
    });

    const content = response.getContentText("UTF-8");

    return ContentService
      .createTextOutput(content)
      .setMimeType(ContentService.MimeType.CSV);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
