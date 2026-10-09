import { getDocuments } from "@/apis/documentApis";
import { getUsers } from "@/apis/userApis";

export async function getDashboard(signal?: AbortSignal) {
  const [recent, published, draft, hidden, archived, users] = await Promise.all([
    getDocuments({ itemsPerPage: 100 }, signal),
    getDocuments({ itemsPerPage: 1, publication_status: "published" }, signal),
    getDocuments({ itemsPerPage: 1, publication_status: "draft" }, signal),
    getDocuments({ itemsPerPage: 1, publication_status: "hidden" }, signal),
    getDocuments({ itemsPerPage: 1, publication_status: "archived" }, signal),
    getUsers({ itemsPerPage: 4 }, signal),
  ]);
  const counts = {
    published: published.meta?.total || 0, draft: draft.meta?.total || 0,
    hidden: hidden.meta?.total || 0, archived: archived.meta?.total || 0,
  };
  return { recent: recent.data, users: users.data, userCount: users.meta?.total || 0,
    counts, documentCount: Object.values(counts).reduce((sum, count) => sum + count, 0) };
}
