/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  transpilePackages: ["@milesai/ui-shared"],
  async redirects() {
    return [
      { source: "/agents", destination: "/workbench/agents", permanent: false },
      { source: "/agents/chat", destination: "/workbench/agents/chat", permanent: false },
      { source: "/compliance", destination: "/workbench/compliance", permanent: false },
      { source: "/prompts", destination: "/workbench/prompts", permanent: false },
      { source: "/models", destination: "/workbench/models", permanent: false },
      { source: "/hooks", destination: "/workbench/hooks", permanent: false },
      { source: "/tools", destination: "/workbench/tools", permanent: false },
      { source: "/skills", destination: "/workbench/skills", permanent: false },
      { source: "/mcp", destination: "/workbench/mcp", permanent: false },
      { source: "/kb", destination: "/workbench/kb", permanent: false },
      { source: "/kb/:id", destination: "/workbench/kb/:id", permanent: false },
      { source: "/attachments", destination: "/workbench/attachments", permanent: false },
      { source: "/flows", destination: "/workbench/flows", permanent: false },
      { source: "/flows/:id/edit", destination: "/workbench/flows/:id/edit", permanent: false },
      { source: "/tasks", destination: "/workbench/tasks", permanent: false },
      { source: "/monitor", destination: "/workbench/monitor", permanent: false },
      { source: "/marketplace", destination: "/workbench/marketplace", permanent: false },
      { source: "/sensitive-words", destination: "/workbench/compliance", permanent: false },
    ];
  },
};

export default nextConfig;
