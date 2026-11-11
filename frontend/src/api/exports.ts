import { useMutation } from "@tanstack/react-query";

import { ApiError } from "@/api/client";

// A binary file, not JSON, so this doesn't go through apiRequest: it reads the file name the
// server chose (Content-Disposition) and hands the browser a normal download.
export function useDownloadAllData() {
  return useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/exports/data");
      if (!response.ok) throw new ApiError(response.status, "");
      const disposition = response.headers.get("content-disposition") ?? "";
      const name = /filename\*=UTF-8''([^;]+)/.exec(disposition);
      const fileName = name ? decodeURIComponent(name[1]) : "autostock-data.xlsx";
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      link.click();
      URL.revokeObjectURL(url);
    },
  });
}
