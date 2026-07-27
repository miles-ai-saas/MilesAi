import { generateAppIcon } from "@milesai/ui-shared/brand/generate-app-icon";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";
export const dynamic = "force-static";

/** output: export 下 metadata icon 的 [[...__metadata_id__]] 需显式给出空 catch-all */
export function generateStaticParams() {
  return [{ __metadata_id__: [] }];
}

export default function AppleIcon() {
  return generateAppIcon(180);
}
