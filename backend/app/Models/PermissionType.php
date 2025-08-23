<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class PermissionType extends Model
{
    use HasFactory, SoftDeletes;
    protected $table = 'permission_types';
    
    protected $fillable = [
        'id',
        'permission_type_name',
        'status',       
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
