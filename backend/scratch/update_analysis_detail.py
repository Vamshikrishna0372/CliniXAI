with open('clinixai-health-flow/src/routes/app.ai-analysis.$id.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    const recId = activeReport?.medicalRecordId;
    const docId = (activeReport as any)?.documentId || (activeReport as any)?.document_id || (recId?.startsWith("DOC-") ? recId : undefined);

    if (docId) {
      apiClient.documents.getFileBlob(docId)
        .then((blob) => {
          if (!isCancelled && blob) {
            currentOriginalUrl = URL.createObjectURL(blob);
            setOriginalBlobUrl(currentOriginalUrl);
          }
        })
        .catch(() => {
          if (!isCancelled) {
            setOriginalBlobUrl(undefined);
          }
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
          if (!isCancelled) {
            setOriginalBlobUrl(undefined);
          }
        });
    }"""

replacement = """    const recId = activeReport?.medicalRecordId;
    const docId = (activeReport as any)?.documentId || (activeReport as any)?.document_id || (recId?.startsWith("DOC-") ? recId : undefined);

    // Stream original image via authenticated endpoint with fallback to document/record blob
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

content_norm = content.replace("\r\n", "\n")
target_norm = target.replace("\r\n", "\n")
replacement_norm = replacement.replace("\r\n", "\n")

if target_norm in content_norm:
    content_norm = content_norm.replace(target_norm, replacement_norm)
    print("Replaced in app.ai-analysis.$id.tsx successfully")
else:
    print("Failed to find target in app.ai-analysis.$id.tsx")

if "\r\n" in content:
    content_norm = content_norm.replace("\n", "\r\n")

with open('clinixai-health-flow/src/routes/app.ai-analysis.$id.tsx', 'w', encoding='utf-8') as f:
    f.write(content_norm)
