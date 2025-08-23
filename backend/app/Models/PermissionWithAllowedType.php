<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class PermissionWithAllowedType extends Model
{
    use HasFactory, SoftDeletes;
    protected $table = 'permission_with_allowed_types';
    protected $fillable = [
        'id',
        'permission_type_id',
        'permission_id',
        'status',
        'approved_at',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
