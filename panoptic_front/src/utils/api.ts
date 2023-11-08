import { AxiosResponse } from "axios"

export const saveFile = async (response: AxiosResponse, title: string) => {
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', title)
    document.body.appendChild(link)
    link.click()
}