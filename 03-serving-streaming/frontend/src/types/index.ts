export type VideoStatus = 'uploading' | 'processing' | 'ready' | 'failed'
export type Visibility = 'public' | 'unlisted' | 'private'
export type VideoSource = 'native' | 'youtube'

export interface ChannelSummary {
  id: string
  displayName: string
  avatarUrl: string | null
}

export interface Video {
  id: string
  ownerId: string
  title: string
  description: string
  thumbnailUrl: string | null
  manifestUrl: string | null
  status: VideoStatus
  durationSeconds: number
  viewCount: number
  likeCount: number
  dislikeCount: number
  visibility: Visibility
  source: VideoSource
  externalId: string | null
  createdAt: string
  updatedAt: string
  channel: ChannelSummary
}

export interface Comment {
  id: string
  videoId: string
  authorId: string
  authorName: string
  authorAvatarUrl: string | null
  text: string
  createdAt: string
  parentId: string | null
}

export interface Channel {
  id: string
  displayName: string
  avatarUrl: string | null
  bio: string
  subscriberCount: number
  videos: Video[]
}

export type NotificationType = 'video.ready' | 'video.failed' | 'comment' | 'subscriber'

export interface AppNotification {
  id: string
  type: NotificationType
  title: string
  body: string
  videoId: string | null
  read: boolean
  createdAt: string
}

export interface Paginated<T> {
  items: T[]
  nextCursor: string | null
}

export interface PresignedPart {
  partNumber: number
  url: string
}

export interface PresignResponse {
  videoId: string
  uploadId: string
  key: string
  partSize: number
  parts: PresignedPart[]
  expiresAt: string
}

export interface ApiError {
  error: {
    code: string
    message: string
  }
}
