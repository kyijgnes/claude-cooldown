package com.kyijgnes.cooldown.update

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import java.io.File

/**
 * 받은 APK 하나를 시스템 설치 화면에 넘기는 통로(`content://…update/파일이름`).
 *
 * androidx 의 FileProvider 를 들이지 않으려고 직접 둔다(이 앱은 androidx 를 work 하나만 쓴다).
 * 내보내지 않고(exported=false) 설치 화면에만 읽기 권한을 잠깐 준다. `cacheDir/update/` 밖은 못 연다.
 */
class ApkProvider : ContentProvider() {

    override fun onCreate(): Boolean = true

    override fun getType(uri: Uri): String = MIME

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        val f = fileFor(uri) ?: throw java.io.FileNotFoundException(uri.toString())
        return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY)
    }

    override fun query(
        uri: Uri, projection: Array<out String>?, selection: String?,
        selectionArgs: Array<out String>?, sortOrder: String?,
    ): Cursor? {
        val f = fileFor(uri) ?: return null
        val c = MatrixCursor(arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE))
        c.addRow(arrayOf<Any>(f.name, f.length()))
        return c
    }

    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0

    private fun fileFor(uri: Uri): File? {
        val ctx = context ?: return null
        val name = uri.lastPathSegment ?: return null
        val dir = dir(ctx).canonicalFile
        val f = File(dir, name).canonicalFile
        return if (f.parentFile == dir && f.isFile) f else null
    }

    companion object {
        const val MIME = "application/vnd.android.package-archive"

        fun dir(ctx: Context): File = File(ctx.cacheDir, "update")

        fun uriFor(ctx: Context, f: File): Uri =
            Uri.Builder().scheme("content").authority("${ctx.packageName}.update").appendPath(f.name).build()
    }
}
