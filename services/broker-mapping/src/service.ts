/**
 * BrokerMappingService — Robinhood symbol mapping
 * Stub: maps option symbols between OCC format and Robinhood IDs.
 */
import { createLogger } from "@zoe/shared";

const log = createLogger("broker-mapping");

export class BrokerMappingService {
  constructor() {
    log.info("BrokerMappingService initialized (stub)");
  }

  async resolveSymbol(_occSymbol: string): Promise<string | null> {
    log.warn("resolveSymbol called on stub — returning null");
    return null;
  }
}
