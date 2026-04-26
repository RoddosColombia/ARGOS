export interface SocialAccount {
  id: string;
  plataforma: string;
  username: string;
  seguidores: number;
  engagement_rate: number;
  descripcion: string;
  url_perfil: string;
  relevancia_score: number;
  fuente_query: string;
}

export interface SocialPost {
  id: string;
  plataforma: string;
  username: string;
  post_external_id: string;
  url_post: string;
  descripcion: string;
  vistas: number;
  likes: number;
  comentarios: number;
  hashtags: string[];
  fecha_publicacion: string | null;
}
