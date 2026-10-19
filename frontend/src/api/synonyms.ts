import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

// Groups of words that mean the same part, used by part search.
export type SynonymList = { groups: string[][] };

const synonymsQueryKey = ["synonyms"];

export function useSynonyms() {
  return useQuery({ queryKey: synonymsQueryKey, queryFn: () => apiRequest<SynonymList>("/api/synonyms") });
}

export function useSaveSynonyms() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (list: SynonymList) => apiRequest<SynonymList>("/api/synonyms", { method: "PUT", body: list }),
    onSuccess: (list) => {
      queryClient.setQueryData(synonymsQueryKey, list);
      queryClient.invalidateQueries({ queryKey: ["stock"] });
      queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}
