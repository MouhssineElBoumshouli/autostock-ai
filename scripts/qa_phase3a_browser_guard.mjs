export const EXPECTED_QA_DATABASE = "autostock_phase3a_qa";

export function assertDisposableQADatabase(database) {
    if (database !== EXPECTED_QA_DATABASE) {
        throw new Error(
            `Refusing browser QA writes: AUTOSTOCK_QA_DB must be exactly ${EXPECTED_QA_DATABASE}. `
            + "This runner only writes to its disposable Phase 3A QA database."
        );
    }
}
