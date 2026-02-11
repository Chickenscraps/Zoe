/**
 * @zoe/research — Research ingestion pipeline
 */
export { ResearchService, type ResearchConfig } from "./service.js";
export {
  fetchGoogleTrends,
  fetchXPosts,
  fetchBloomberg,
  type TrendsConfig,
  type XConfig,
  type BloombergConfig,
} from "./connectors.js";
