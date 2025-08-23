<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class ResourceMaterial extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'folder_id',
        'folder_name',
        'file_name',
        'file_type',
        'file',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
