import { generateAppIcon } from "@milesai/ui-shared/brand/generate-app-icon";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return generateAppIcon(32);
}
