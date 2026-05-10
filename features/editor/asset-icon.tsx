import { getAssetById } from '@/lib/assets';
import type { VectorAsset } from '@/lib/types';

export function AssetIcon({ asset, className = '' }: { asset: VectorAsset; className?: string }) {
  return <span className={`block text-current ${className}`} dangerouslySetInnerHTML={{ __html: asset.inlineSvg }} />;
}

export function PlacedAssetIcon({ assetId, className = '' }: { assetId: string; className?: string }) {
  const asset = getAssetById(assetId);
  if (!asset) return null;
  return <AssetIcon asset={asset} className={className} />;
}
