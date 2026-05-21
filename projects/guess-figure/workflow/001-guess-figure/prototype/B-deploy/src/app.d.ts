// See https://svelte.dev/docs/kit/types#app
declare global {
  namespace App {
    interface Platform {
      env?: {
        YUNWU_API_KEY?: string;
        YUNWU_BASE_URL?: string;
        LLM_MODEL?: string;
      };
    }
  }
}

export {};
