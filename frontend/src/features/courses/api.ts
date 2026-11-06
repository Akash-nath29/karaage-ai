import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, send } from '@/lib/api'

export type Course = {
  id: string
  workspace_id: string
  title: string
  code: string
  term: string
  description: string
  created_at: string
}
export type CourseInput = Pick<Course, 'title' | 'code' | 'term' | 'description'>

export const useCourses = (workspaceId: string) =>
  useQuery({
    queryKey: ['courses', { workspaceId }],
    queryFn: () => api<Course[]>(`/workspaces/${workspaceId}/courses`),
  })

export const useCourse = (id: string) =>
  useQuery({ queryKey: ['courses', id], queryFn: () => api<Course>(`/courses/${id}`) })

// Deletes pass refetchType 'none': mark caches stale without refetching the just-deleted
// item while its page is still mounted (that refetch 404s and would hold the mutation pending).
function useCourseMutation<In, Out>(fn: (input: In) => Promise<Out>, refetchType: 'active' | 'none' = 'active') {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ['courses'], refetchType }) })
}

export const useCreateCourse = (workspaceId: string) =>
  useCourseMutation((body: CourseInput) => api<Course>(`/workspaces/${workspaceId}/courses`, send('POST', body)))

export const useUpdateCourse = (id: string) =>
  useCourseMutation((body: Partial<CourseInput>) => api<Course>(`/courses/${id}`, send('PATCH', body)))

export const useDeleteCourse = (id: string) => useCourseMutation(() => api<void>(`/courses/${id}`, send('DELETE')), 'none')

export const courseFields = [
  { name: 'title', label: 'Course title', required: true },
  { name: 'code', label: 'Course code' },
  { name: 'term', label: 'Academic year or semester' },
  { name: 'description', label: 'Description', multiline: true },
]
