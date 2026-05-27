import figures from "$lib/data/figures.json";
import intros from "$lib/data/turtle-intros.json";
import { createTurtleSoupRound } from "$lib/turtle-soup-state";
import type { Figure } from "$lib/types";
import type { PageLoad } from "./$types";

export const load = (() => {
  return {
    initialRound: createTurtleSoupRound({
      figures: figures as Figure[],
      intros: intros as Record<string, string>,
      createSessionId: () => crypto.randomUUID(),
    }),
  };
}) satisfies PageLoad;
