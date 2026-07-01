/** @type {import('next').NextConfig} */
// standalone jen pro Docker (nastav NEXT_OUTPUT_STANDALONE=true). Na Vercelu se
// nepoužívá — tam vlastní standalone výstup způsobí chybu ve fázi build traces.
const nextConfig = {
  output: process.env.NEXT_OUTPUT_STANDALONE === "true" ? "standalone" : undefined,
};

export default nextConfig;
