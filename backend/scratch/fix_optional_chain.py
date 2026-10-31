import os

path = os.path.join("clinixai-health-flow", "src", "routes", "app.ai-analysis.$id.tsx")
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

target = """    // Stream original image via authenticated endpoint with fallback to document/record blob
    apiClient.ai.getOriginalImageBlob(activeReport.id)
      .then((blob) => {
        if (!isCancelled && blob) {
          currentOriginalUrl = URL.createObjectURL(blob);
          setOriginalBlobUrl(currentOriginalUrl);
        }
      })
      .catch(() => {
        if (docId) {
          apiClient.documents.getFileBlob(docId)
            .then((blob) => {
              if (!isCancelled && blob) {
                currentOriginalUrl = URL.createObjectURL(blob);
                setOriginalBlobUrl(currentOriginalUrl);
              }
            })
            .catch(() => {
              if (!isCancelled) setOriginalBlobUrl(undefined);
            });
        } else if (recId) {
          apiClient.medicalRecords.getFileBlob(recId)
            .then((blob) => {
              if (!isCancelled && blob) {
                currentOriginalUrl = URL.createObjectURL(blob);
                setOriginalBlobUrl(currentOriginalUrl);
              }
            })
            .catch(() => {
              if (!isCancelled) setOriginalBlobUrl(undefined);
            });
        } else {
          if (!isCancelled) setOriginalBlobUrl(undefined);
        }
      });"""

replacement = """    // Stream original image via authenticated endpoint with fallback to document/record blob
    if (activeReport?.id) {
      apiClient.ai.getOriginalImageBlob(activeReport.id)
        .then((blob) => {
          if (!isCancelled && blob) {
            currentOriginalUrl = URL.createObjectURL(blob);
            setOriginalBlobUrl(currentOriginalUrl);
          }
        })
        .catch(() => {
          if (docId) {
            apiClient.documents.getFileBlob(docId)
              .then((blob) => {
                if (!isCancelled && blob) {
                  currentOriginalUrl = URL.createObjectURL(blob);
                  setOriginalBlobUrl(currentOriginalUrl);
                }
              })
              .catch(() => {
                if (!isCancelled) setOriginalBlobUrl(undefined);
              });
          } else if (recId) {
            apiClient.medicalRecords.getFileBlob(recId)
              .then((blob) => {
                if (!isCancelled && blob) {
                  currentOriginalUrl = URL.createObjectURL(blob);
                  setOriginalBlobUrl(currentOriginalUrl);
                }
              })
              .catch(() => {
                if (!isCancelled) setOriginalBlobUrl(undefined);
              });
          } else {
            if (!isCancelled) setOriginalBlobUrl(undefined);
          }
        });
    }"""

if target in text:
    text = text.replace(target, replacement)
    print("Replaced with LF!")
elif target.replace("\n", "\r\n") in text:
    text = text.replace(target.replace("\n", "\r\n"), replacement.replace("\n", "\r\n"))
    print("Replaced with CRLF!")
else:
    print("Target not found directly, checking partials...")
    old_call = "apiClient.ai.getOriginalImageBlob(activeReport.id)"
    assert old_call in text
    # Let's inspect where it is
    idx = text.find(old_call)
    print("Found at index:", idx)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Updated successfully.")

